<?php
/**
 * Instalación nueva de Central en Ubuntu Server, exclusivamente desde CLI.
 * No actualiza ni sobrescribe instalaciones existentes. No imprime credenciales.
 */
declare(strict_types=1);
if (PHP_SAPI !== 'cli') {
    http_response_code(404);
    exit;
}

function abort_setup(string $message): never {
    fwrite(STDERR, "No se pudo instalar Central: $message\n");
    exit(1);
}
function private_directory(string $path): string {
    if (!str_starts_with($path, '/') || is_link($path)) {
        throw new RuntimeException('Las rutas privadas deben ser absolutas y no enlaces simbólicos.');
    }
    if (!is_dir($path) && !mkdir($path, 0700, true) && !is_dir($path)) {
        throw new RuntimeException('No se pudo crear el directorio privado.');
    }
    $real = realpath($path);
    $public = realpath(__DIR__.'/../cpanel');
    if (!$real || !$public || !is_writable($real) || $real === $public ||
        str_starts_with($real, $public.'/')) {
        throw new RuntimeException('Los datos y la configuración deben quedar fuera del directorio público.');
    }
    return $real;
}
function read_admin_password(bool $fromStdin): string {
    if ($fromStdin) return rtrim((string)stream_get_contents(STDIN), "\r\n");
    if (!stream_isatty(STDIN)) {
        throw new RuntimeException('Use una terminal interactiva o --password-stdin.');
    }
    fwrite(STDERR, 'Contraseña del administrador (12–500 caracteres): ');
    exec('stty -echo', $output, $status);
    if ($status !== 0) throw new RuntimeException('No se puede ocultar la contraseña en esta terminal.');
    try {
        $password = rtrim((string)fgets(STDIN), "\r\n");
        fwrite(STDERR, "\nRepita la contraseña: ");
        $confirmation = rtrim((string)fgets(STDIN), "\r\n");
    } finally {
        exec('stty echo');
        fwrite(STDERR, "\n");
    }
    if ($password !== $confirmation) throw new RuntimeException('Las contraseñas no coinciden.');
    return $password;
}

$options = getopt('', ['help', 'config:', 'data-dir:', 'base-url:', 'school:', 'name:', 'email:', 'password-stdin']);
foreach ($options as $option => $value) {
    if (is_array($value)) abort_setup("La opción --$option no puede repetirse.");
}
if (isset($options['help'])) {
    echo "Instalar Central (solo instalaciones nuevas):\n".
         "php central/ubuntu/setup.php --base-url=https://conta.ejemplo.org ".
         "--school='Centro educativo' --name='Administrador' --email=admin@ejemplo.org\n".
         "Opciones: --config=/etc/conta-fp360/config.php --data-dir=/var/lib/conta-fp360\n".
         "La contraseña se pide oculta; --password-stdin permite recibirla por entrada estándar.\n";
    exit(0);
}
$pdo = null;
$dbPath = null;
$createdDb = false;
$configHandle = null;
$configPath = null;
$createdConfig = false;
umask(0077);
try {
    if (PHP_VERSION_ID < 80200) throw new RuntimeException('Se requiere PHP 8.2 o superior.');
    foreach (['pdo_sqlite', 'sqlite3', 'zip', 'mbstring', 'fileinfo'] as $extension) {
        if (!extension_loaded($extension)) throw new RuntimeException("Falta la extensión PHP $extension.");
    }
    $url = rtrim((string)($options['base-url'] ?? ''), '/');
    $parts = parse_url($url);
    if (!filter_var($url, FILTER_VALIDATE_URL) || !$parts || empty($parts['host']) ||
        isset($parts['user']) || isset($parts['query']) || isset($parts['fragment']) ||
        !(($parts['scheme'] ?? '') === 'https' ||
          (($parts['scheme'] ?? '') === 'http' && in_array($parts['host'], ['localhost', '127.0.0.1', '[::1]'], true)))) {
        throw new RuntimeException('--base-url debe usar HTTPS; HTTP solo se admite en loopback para pruebas.');
    }
    $school = trim((string)($options['school'] ?? ''));
    $name = trim((string)($options['name'] ?? ''));
    $email = strtolower(trim((string)($options['email'] ?? '')));
    if ($school === '' || strlen($school) > 255 || $name === '' || strlen($name) > 255 ||
        strlen($email) > 240 || !filter_var($email, FILTER_VALIDATE_EMAIL)) {
        throw new RuntimeException('Indique --school, --name y un --email válido.');
    }
    $password = read_admin_password(isset($options['password-stdin']));
    if (strlen($password) < 12 || strlen($password) > 500 || trim($password) !== $password) {
        throw new RuntimeException('La contraseña debe tener 12–500 caracteres, sin espacios iniciales o finales.');
    }
    $data = private_directory((string)($options['data-dir'] ?? '/var/lib/conta-fp360'));
    $requestedConfig = (string)($options['config'] ?? '/etc/conta-fp360/config.php');
    if (is_link($requestedConfig) || file_exists($requestedConfig)) {
        throw new RuntimeException('La configuración ya existe. No se sobrescribirá.');
    }
    $configPath = private_directory(dirname($requestedConfig)).'/'.basename($requestedConfig);
    $dbPath = $data.'/conta-central.sqlite3';
    if (file_exists($dbPath) || is_link($dbPath)) {
        throw new RuntimeException('SQLite ya existe. No se sobrescribirá; haga una copia antes de actualizar.');
    }
    $uploads = $data.'/packages';
    if (file_exists($uploads) || is_link($uploads)) {
        throw new RuntimeException('La carpeta de paquetes ya existe. Revise la instalación antes de continuar.');
    }
    // Creación exclusiva: una segunda ejecución no puede truncar SQLite.
    $reservation = @fopen($dbPath, 'x');
    if ($reservation === false) throw new RuntimeException('No se pudo reservar una base SQLite nueva.');
    $createdDb = true;
    fclose($reservation);
    if (!mkdir($uploads, 0700)) throw new RuntimeException('No se pudo crear la carpeta de paquetes.');
    $pdo = new PDO('sqlite:'.$dbPath, null, null, [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
    $pdo->exec('PRAGMA foreign_keys=ON; PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;');
    $schema = file_get_contents(__DIR__.'/../cpanel/schema.sql');
    if ($schema === false) throw new RuntimeException('No se encuentra el esquema original de Central.');
    $pdo->beginTransaction();
    $pdo->exec($schema);
    require_once __DIR__.'/../cpanel/features.php';
    ensure_central_features($pdo);
    $pdo->prepare('INSERT INTO schools(name) VALUES(?)')->execute([$school]);
    $schoolId = (int)$pdo->lastInsertId();
    $pdo->prepare('INSERT INTO users(school_id,email,display_name,role,passhash) VALUES(?,?,?,?,?)')
        ->execute([$schoolId, $email, $name, 'admin', password_hash($password, PASSWORD_DEFAULT)]);
    unset($password);
    $pdo->commit();
    $pdo->exec('PRAGMA wal_checkpoint(TRUNCATE)');
    $pdo = null;
    $config = [
        'base_url' => $url, 'db_path' => $dbPath, 'upload_dir' => $uploads,
        'token_hours' => 8, 'platform_owner_email' => $email,
        'require_curriculum_catalog' => true,
        'max_package_bytes' => 25 * 1024 * 1024, 'max_submission_bytes' => 3 * 1024 * 1024,
    ];
    $configHandle = @fopen($configPath, 'x');
    if ($configHandle === false) throw new RuntimeException('No se pudo crear la configuración privada.');
    $createdConfig = true;
    $encoded = "<?php\n// Configuración privada de CONTA FP360 Central. No publicar.\nreturn ".var_export($config, true).";\n";
    if (fwrite($configHandle, $encoded) !== strlen($encoded) || !fflush($configHandle)) {
        throw new RuntimeException('Escritura incompleta de la configuración.');
    }
    fclose($configHandle);
    $configHandle = null;
    echo "Central instalado. Configuración y SQLite fuera del directorio público.\n".
         "Ajuste propietario/permisos de Apache según UBUNTU_SERVER.md y active HTTPS antes de acceder.\n";
} catch (Throwable $error) {
    if ($pdo && $pdo->inTransaction()) $pdo->rollBack();
    $pdo = null;
    if (is_resource($configHandle)) fclose($configHandle);
    if ($createdConfig && $configPath) @unlink($configPath);
    if ($createdDb && $dbPath) {
        foreach (['', '-wal', '-shm'] as $suffix) @unlink($dbPath.$suffix);
        if (isset($uploads)) @rmdir($uploads);
    }
    abort_setup($error->getMessage());
}
