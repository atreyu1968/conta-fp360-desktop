<?php
/**
 * CONTA FP360 Central — instalador asistido, edición 2.4.
 *
 * No exige config.php preexistente. Obtiene una autorización de instalación
 * almacenada fuera de la web, detecta el directorio privado de cPanel,
 * comprueba extensiones y repara una ruta de datos inválida sin sobrescribir
 * bases de datos existentes. No publica claves por HTTP.
 */
declare(strict_types=1);
require __DIR__.'/bootstrap.php';
header('Content-Type: text/html; charset=utf-8');
header('X-Frame-Options: DENY');
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
header('Cache-Control: no-store');
header("Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'");

function setup_inside(string $path, string $parent): bool {
    return $path === $parent || str_starts_with($path, rtrim($parent, '/').'/');
}
function setup_home(): string {
    $web=realpath(__DIR__);
    if (!$web) throw new RuntimeException('No se pudo localizar la carpeta de la aplicación.');
    $choices=[];
    foreach ([getenv('HOME') ?: '', (string)($_SERVER['HOME']??'')] as $candidate) {
        if ($candidate !== '') $choices[]=$candidate;
    }
    if (preg_match('~^(.+?)/public_html(?:/|$)~', $web, $m)) $choices[]=$m[1];
    $choices[]=dirname($web);
    foreach ($choices as $candidate) {
        $real=realpath($candidate);
        if (!$real || !is_dir($real) || !is_writable($real)) continue;
        if (in_array($real,['/','/home','/var','/srv','/tmp','/usr','/www'],true)) continue;
        if (setup_inside($real,$web)) continue;
        if (str_contains($real, '/public_html') || str_contains($real, '/httpdocs')) continue;
        return $real;
    }
    throw new RuntimeException('No encuentro una carpeta personal de cPanel con permiso de escritura. Compruebe el directorio HOME del alojamiento y los permisos del usuario PHP.');
}
function setup_private(string $home): string {
    $path=rtrim($home,'/').'/.conta-fp360';
    if (is_link($path)) throw new RuntimeException('La carpeta privada es un enlace simbólico; no puede usarse para la instalación.');
    if (!is_dir($path) && !@mkdir($path,0700,true) && !is_dir($path)) {
        throw new RuntimeException('No es posible crear .conta-fp360 en la carpeta personal. Compruebe propietario y permisos desde cPanel.');
    }
    if (!is_writable($path) || !is_readable($path)) {
        throw new RuntimeException('La carpeta privada .conta-fp360 no permite lectura y escritura desde PHP.');
    }
    @chmod($path,0700);
    return $path;
}
function setup_key(string $private): string {
    $file=$private.'/instalacion.clave';
    if (is_link($file)) throw new RuntimeException('Archivo de autorización inseguro.');
    if (!is_file($file)) {
        $handle=@fopen($file,'x');
        if ($handle===false && !is_file($file)) throw new RuntimeException('No puedo crear la clave privada de autorización.');
        if ($handle!==false) {
            $key=bin2hex(random_bytes(32));
            if (fwrite($handle,$key."\n")!==strlen($key)+1) {
                fclose($handle);@unlink($file);
                throw new RuntimeException('No se pudo escribir la clave privada.');
            }
            fclose($handle);@chmod($file,0600);
        }
    }
    $key=@file_get_contents($file);
    if (!is_string($key) || strlen(trim($key))<32) throw new RuntimeException('La clave de instalación está vacía o incompleta.');
    return trim($key);
}
function setup_existing(): ?array {
    $file=__DIR__.'/config.php';
    if (is_link($file)) throw new RuntimeException('config.php no puede ser un enlace simbólico.');
    if (!is_file($file)) return null;
    try {
        $cfg=require $file;
        if (!is_array($cfg)) throw new RuntimeException('config.php no devuelve un array válido.');
        return $cfg;
    } catch (Throwable $e) {
        error_log('[CONTA FP360 instalación] Configuración anterior dañada: '.$e->getMessage());
        // Se conserva una copia en la carpeta privada antes de regenerarla.
        return ['_invalid_config'=>true];
    }
}
function setup_installed(?array $cfg): bool {
    if (!$cfg || !isset($cfg['db_path']) || !is_string($cfg['db_path']) || !is_file($cfg['db_path'])) return false;
    try {
        $pdo=new PDO('sqlite:'.$cfg['db_path'],null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
        $tables=$pdo->query("SELECT name FROM sqlite_master WHERE type='table' AND name='users'");
        if ($tables===false || !$tables->fetchColumn()) return false;
        return (int)$pdo->query('SELECT COUNT(*) FROM users')->fetchColumn()>0;
    } catch (Throwable $e) {
        error_log('[CONTA FP360 instalación] No se pudo verificar base existente: '.$e->getMessage());
        return false;
    }
}
function setup_requirements(string $private): array {
    $checks=[
        'PHP 8.2 o superior'=>PHP_VERSION_ID>=80200,
        'PDO con controlador SQLite'=>class_exists('PDO') && in_array('sqlite',PDO::getAvailableDrivers(),true),
        'Extensión SQLite3'=>class_exists('SQLite3'),
        'Extensión ZIP'=>class_exists('ZipArchive'),
        'Carpeta de datos privada escribible'=>is_dir($private) && is_writable($private),
        'Carpeta web escribible para config.php'=>is_file(__DIR__.'/config.php') || is_writable(__DIR__),
        'Esquema SQL disponible'=>is_file(__DIR__.'/schema.sql') && is_readable(__DIR__.'/schema.sql'),
    ];
    return $checks;
}
function setup_is_path_writable(string $path): bool {
    if ($path==='' || $path[0]!=='/') return false;
    $dir=dirname($path);
    if (is_dir($dir)) return is_writable($dir);
    while (!is_dir($dir) && dirname($dir)!==$dir) $dir=dirname($dir);
    return is_dir($dir) && is_writable($dir);
}
function setup_looks_private(string $path): bool {
    $root=realpath(__DIR__);
    if (!$root || $path==='' || $path[0]!=='/') return false;
    $dir=dirname($path);
    $probe=$dir;
    while (!file_exists($probe) && dirname($probe)!==$probe) $probe=dirname($probe);
    $parent=realpath($probe);
    if (!$parent || setup_inside($parent,$root)) return false;
    // No aceptar bases de datos dentro de otros document roots conocidos.
    if (preg_match('~/(public_html|httpdocs|htdocs|www)(/|$)~i',$path)) return false;
    return true;
}
function setup_site_url(): string {
    $host=strtolower((string)($_SERVER['HTTP_HOST']??''));
    if (!preg_match('/^[a-z0-9.-]+(?::[0-9]{1,5})?$/D',$host)) throw new RuntimeException('Host HTTP no válido.');
    $https=!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS']!=='off';
    if (!$https && !in_array(explode(':',$host)[0],['localhost','127.0.0.1'],true)) {
        throw new RuntimeException('El instalador debe ejecutarse mediante HTTPS.');
    }
    return ($https?'https':'http').'://'.$host;
}
function setup_write_config(array $config, string $private, bool $replacement): void {
    $file=__DIR__.'/config.php';
    if (is_link($file)) throw new RuntimeException('config.php es un enlace simbólico.');
    if ($replacement && is_file($file)) {
        $backup=$private.'/config-previa-'.gmdate('Ymd-His').'-'.bin2hex(random_bytes(4)).'.bak';
        if (!@copy($file,$backup)) throw new RuntimeException('No pude hacer una copia privada de la configuración anterior.');
        @chmod($backup,0600);
    }
    $encoded="<?php\n/** Generado por el instalador CONTA FP360 Central. No publicar. */\nreturn ".var_export($config,true).";\n";
    $temp=$file.'.setup-'.bin2hex(random_bytes(8)).'.tmp';
    $handle=@fopen($temp,'x');
    if ($handle===false) throw new RuntimeException('No puedo escribir config.php. Compruebe permisos de la carpeta de Central.');
    try {
        @chmod($temp,0600);
        if (fwrite($handle,$encoded)!==strlen($encoded)) throw new RuntimeException('Escritura incompleta de config.php.');
        fflush($handle);
        fclose($handle);
        $handle=null;
        if (!@rename($temp,$file)) throw new RuntimeException('No se pudo activar config.php.');
        @chmod($file,0600);
    } finally {
        if (is_resource($handle)) fclose($handle);
        if (is_file($temp)) @unlink($temp);
    }
}
function setup_h(string $value): string {return htmlspecialchars($value,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');}

$message='';
$error='';
$complete=false;
$installed=false;
$checks=[];
$private='';
$legacy=false;
try {
    $site=setup_site_url(); // Exigir HTTPS ANTES de recibir contraseñas.
    $home=setup_home();
    $private=setup_private($home);
    $authKey=setup_key($private);
    $existing=setup_existing();
    $installed=setup_installed($existing);
    if ($installed) {
        http_response_code(403);
        $message='Central ya está instalada. Por seguridad, elimine install.php desde cPanel y acceda a index.php.';
    } else {
        $checks=setup_requirements($private);
        $legacy=$existing!==null;
        if ($_SERVER['REQUEST_METHOD']==='POST') {
            $submitted=(string)($_POST['secret']??'');
            $legacySecret=is_string($existing['install_secret']??null) ? $existing['install_secret'] : '';
            $authorized=(strlen($submitted)>=24 && hash_equals($authKey,$submitted))
                || (strlen($legacySecret)>=24 && !str_starts_with($legacySecret,'REEMPLAZAR') && hash_equals($legacySecret,$submitted));
            if (!$authorized) throw new RuntimeException('Clave de autorización incorrecta. Abra .conta-fp360/instalacion.clave desde el administrador de archivos de cPanel.');
            $invalid=array_keys(array_filter($checks,static fn($ok)=>!$ok));
            if ($invalid) throw new RuntimeException('Faltan requisitos del alojamiento: '.implode(', ',$invalid).'.');
            $school=trim((string)($_POST['school']??''));
            $person=trim((string)($_POST['name']??''));
            $email=strtolower(trim((string)($_POST['email']??'')));
            $password=(string)($_POST['password']??'');
            if (strlen($school)<3 || strlen($person)<3 || !filter_var($email,FILTER_VALIDATE_EMAIL) || strlen($password)<12)
                throw new RuntimeException('Revise el centro, nombre, correo y contraseña (mínimo 12 caracteres).');
            $defaultDb=$private.'/conta-central.sqlite3';
            $oldDb=is_string($existing['db_path']??null)?$existing['db_path']:'';
            $oldUploads=is_string($existing['upload_dir']??null)?$existing['upload_dir']:'';
            if ($oldDb!=='' && is_file($oldDb) && !setup_looks_private($oldDb)) {
                throw new RuntimeException('La base de datos existente está en una ruta pública o insegura. No se modificará automáticamente.');
            }
            $useOld=$oldDb!=='' && $oldUploads!=='' &&
                setup_looks_private($oldDb) && setup_looks_private($oldUploads) &&
                setup_is_path_writable($oldDb) && setup_is_path_writable($oldUploads);
            if ($oldDb!=='' && is_file($oldDb) && !$useOld) {
                throw new RuntimeException('Existe una base de datos previa en una ruta que no puedo usar. No la moveré ni sustituiré automáticamente.');
            }
            $dbPath=$useOld?$oldDb:$defaultDb;
            $uploadDir=$useOld?$oldUploads:$private.'/packages';
            if (!setup_looks_private($dbPath) || !setup_looks_private($uploadDir)) {
                throw new RuntimeException('La ubicación de datos no está fuera de la web. Instalación cancelada.');
            }
            if (!is_dir(dirname($dbPath)) && !@mkdir(dirname($dbPath),0700,true) && !is_dir(dirname($dbPath))) {
                throw new RuntimeException('No puedo crear la carpeta privada para SQLite.');
            }
            if (!is_dir($uploadDir) && !@mkdir($uploadDir,0700,true) && !is_dir($uploadDir)) {
                throw new RuntimeException('No puedo crear el directorio privado de paquetes.');
            }
            if (!is_writable(dirname($dbPath)) || !is_writable($uploadDir)) {
                throw new RuntimeException('Las carpetas privadas no permiten escribir desde PHP.');
            }
            // Validación REAL de SQLite antes de escribir la configuración definitiva.
            $probe=$private.'/prueba-'.bin2hex(random_bytes(6)).'.sqlite3';
            try {
                $test=new PDO('sqlite:'.$probe,null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
                $test->exec('CREATE TABLE comprobacion (id INTEGER)');
                $test=null;
            } finally {
                @unlink($probe);
                @unlink($probe.'-wal');
                @unlink($probe.'-shm');
            }
            $config=$existing??[];
            $config['install_secret']=(is_string($existing['install_secret']??null) && strlen($existing['install_secret'])>=24 && !str_starts_with($existing['install_secret'],'REEMPLAZAR'))
                ?$existing['install_secret']:bin2hex(random_bytes(32));
            $config['base_url']=$site;
            $config['db_path']=$dbPath;
            $config['upload_dir']=$uploadDir;
            $config['token_hours']=(int)($existing['token_hours']??8);
            $config['platform_owner_email']=$email;
            $config['require_curriculum_catalog']=(bool)($existing['require_curriculum_catalog']??true);
            $config['max_package_bytes']=(int)($existing['max_package_bytes']??25*1024*1024);
            $config['max_submission_bytes']=(int)($existing['max_submission_bytes']??3*1024*1024);
            // Crea o repara automáticamente config.php; conserva copia privada del anterior.
            $needsConfig=($existing===null || $dbPath!==$oldDb || $uploadDir!==$oldUploads ||
                ($existing['base_url']??'')!==$site || ($existing['platform_owner_email']??'')!==$email);
            if ($needsConfig) setup_write_config($config,$private,$existing!==null);
            // SQL sin doble creación de administrador; la tabla puede existir vacía
            // si una instalación previa se interrumpió.
            $pdo=new PDO('sqlite:'.$dbPath,null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC]);
            $pdo->exec('PRAGMA foreign_keys=ON; PRAGMA busy_timeout=5000; PRAGMA journal_mode=WAL;');
            $sql=file_get_contents(__DIR__.'/schema.sql');
            if (!is_string($sql)) throw new RuntimeException('Falta schema.sql.');
            $pdo->exec($sql);
            $pdo->exec('BEGIN IMMEDIATE');
            try {
                if ((int)$pdo->query('SELECT COUNT(*) FROM users')->fetchColumn()>0)
                    throw new RuntimeException('Ya existe un administrador. No se permite volver a instalar.');
                $stmt=$pdo->prepare('INSERT INTO schools(name) VALUES(?)');
                $stmt->execute([$school]);
                $schoolId=(int)$pdo->lastInsertId();
                $stmt=$pdo->prepare('INSERT INTO users(school_id,email,display_name,role,passhash) VALUES(?,?,?,?,?)');
                $stmt->execute([$schoolId,$email,$person,'admin',password_hash($password,PASSWORD_DEFAULT)]);
                $pdo->commit();
            } catch (Throwable $e) {
                if ($pdo->inTransaction()) $pdo->rollBack();
                throw $e;
            }
            @unlink($private.'/instalacion.clave');
            $complete=true;
            $message='Servidor instalado correctamente. La configuración y SQLite ya están creadas en las carpetas adecuadas.';
            // Si el alojamiento permite borrar el script en ejecución, lo retiramos.
            $deleted=@unlink(__FILE__);
            if (!$deleted) $message.=' Elimine install.php manualmente desde cPanel.';
        }
    }
} catch (Throwable $e) {
    error_log('[CONTA FP360 instalación] '.$e->getMessage());
    $error=$e->getMessage();
}
?><!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Asistente de instalación · CONTA FP360 Central</title>
<style>
:root{color-scheme:light}*{box-sizing:border-box}body{font:16px/1.5 system-ui,-apple-system,Arial,sans-serif;background:#f4f7fb;color:#203047;margin:0;padding:30px 16px}
main{max-width:720px;margin:auto}.card{background:white;border:1px solid #dbe4ef;border-radius:16px;padding:26px;box-shadow:0 7px 24px #27394b12;margin:18px 0}
h1{font-size:1.7rem;margin:0 0 6px}h2{font-size:1.17rem}p{margin:8px 0 14px}.muted{color:#5b6673}
label{display:block;font-weight:600;margin:14px 0 6px}input{display:block;width:100%;padding:12px;border:1px solid #9baec2;border-radius:8px;font:inherit;margin-top:5px}
button{border:0;border-radius:8px;background:#184d9c;color:#fff;padding:13px 20px;font:inherit;font-weight:650;cursor:pointer;margin-top:16px}
.notice{padding:13px 15px;border-radius:10px;background:#eaf4ec;border:1px solid #91c69c}
.error{padding:13px 15px;border-radius:10px;background:#fff0f0;border:1px solid #dfa4a4}
table{border-collapse:collapse;width:100%;font-size:.92rem}td{border-bottom:1px solid #e8ecf2;padding:8px 4px}td:last-child{text-align:right;font-weight:700}
code{background:#eaf0f8;padding:2px 5px;border-radius:4px;overflow-wrap:anywhere}a{color:#174b9a}
</style></head><body><main>
<h1>CONTA FP360 Central</h1>
<p class="muted">Instalación asistida PHP/SQLite. Detecta las carpetas privadas y genera <code>config.php</code> automáticamente.</p>
<?php if ($error!==''): ?><div class="error" role="alert"><strong>No se ha completado la instalación:</strong> <?=setup_h($error)?></div><?php endif; ?>
<?php if ($message!==''): ?><div class="notice" role="status"><?=setup_h($message)?></div><?php endif; ?>
<?php if ($complete): ?>
<div class="card"><h2>Instalación completada</h2><p>Ya puedes acceder al panel web. El instalador ha retirado la clave de autorización.</p>
<p><a href="index.php">Abrir CONTA FP360 Central</a></p><p><a href="api.php?r=health">Comprobar conexión de la API</a></p></div>
<?php elseif (!$installed): ?>
<div class="card">
<h2>Comprobación del alojamiento</h2>
<table><tbody>
<?php foreach ($checks as $name=>$ok): ?><tr><td><?=setup_h($name)?></td><td><?=$ok?'Correcto':'Revisar'?></td></tr><?php endforeach; ?>
</tbody></table>
<p class="muted">La carpeta privada se crea en tu cuenta de alojamiento, fuera de la web. No es necesario escribir rutas absolutas.</p>
</div>
<div class="card">
<h2>Autorizar e instalar</h2>
<p>En cPanel → Administrador de archivos, abre tu carpeta personal, activa «Mostrar archivos ocultos» y busca <code>.conta-fp360/instalacion.clave</code>. Copia su contenido en el primer campo. <strong>El código no se muestra por Internet</strong>, para impedir que otro visitante tome el control del servidor.</p>
<?php if ($legacy): ?><p class="muted">Existe un <code>config.php</code> anterior. Si su ruta SQLite es incorrecta, el asistente la corregirá con una copia privada de seguridad, siempre que no haya datos existentes que deban conservarse.</p><?php endif; ?>
<form method="post" action="install.php" autocomplete="off">
<label for="secret">Clave de autorización de cPanel<input id="secret" type="password" name="secret" required minlength="24" autocomplete="off"></label>
<label for="school">Nombre del centro educativo<input id="school" name="school" required minlength="3" maxlength="200" value="<?=setup_h((string)($_POST['school']??''))?>"></label>
<label for="name">Nombre del administrador<input id="name" name="name" required minlength="3" maxlength="200" value="<?=setup_h((string)($_POST['name']??''))?>"></label>
<label for="email">Correo del administrador<input id="email" type="email" name="email" required maxlength="240" value="<?=setup_h((string)($_POST['email']??''))?>"></label>
<label for="password">Contraseña del administrador (12 caracteres o más)<input id="password" type="password" name="password" required minlength="12" autocomplete="new-password"></label>
<button type="submit">Comprobar requisitos e instalar Central</button>
</form></div>
<?php endif; ?>
<footer><p class="muted">CONTA FP360 · Servidor educativo. No cargues datos reales hasta verificar accesos, copias de seguridad y protección de datos.</p></footer>
</main></body></html>
