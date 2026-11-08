#!/usr/bin/env bash
# Actualización segura de una instalación existente de Central en Ubuntu.
# No modifica SQLite, paquetes, configuración ni credenciales.
set -Eeuo pipefail
umask 077

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SOURCE_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
readonly INSTALL_ROOT=/var/www/conta-fp360
readonly DATA_DIR=/var/lib/conta-fp360
readonly CONFIG_FILE=/etc/conta-fp360/config.php
readonly SITE_FILE=/etc/apache2/sites-available/conta-central.conf
readonly SITE_ENABLED=/etc/apache2/sites-enabled/conta-central.conf
readonly BACKUP_ROOT=/var/backups/conta-fp360/updates
readonly LOCK_FILE=/run/lock/conta-central-update.lock

BACKUP_DIR=''
STAGE_ROOT=''
PREVIOUS_ROOT=''
FAILED_ROOT=''
SWITCHED=0

fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Actualiza una instalación existente de CONTA FP360 Central para Ubuntu 24.04.

Uso:
  sudo bash central/ubuntu/update.sh
  sudo /usr/local/sbin/conta-central-update --rollback

La primera forma valida paquetes, configuración, SQLite, paquetes privados y
la clave PayPal; prepara una copia temporal del código y respalda los datos.
La segunda restaura la versión de código anterior. No restaura ni elimina datos.

Opciones:
  --rollback     Volver al código de la última actualización satisfactoria
  --self-test    Probar cambio y restauración en una carpeta temporal
  --help         Mostrar esta ayuda

No use install.sh para actualizar una instalación existente.
EOF
}

switch_release() {
  local live=$1 staged=$2 previous=$3
  [[ -d $live && ! -e $previous && ! -L $previous ]] || return 1
  mv -T -- "$live" "$previous"
  if ! mv -T -- "$staged" "$live"; then
    mv -T -- "$previous" "$live" || return 1
    return 1
  fi
}

restore_release() {
  local live=$1 previous=$2 failed=$3
  [[ -d $previous && ! -e $failed && ! -L $failed ]] || return 1
  if [[ -e $live || -L $live ]]; then mv -T -- "$live" "$failed"; fi
  if ! mv -T -- "$previous" "$live"; then
    if [[ -e $failed || -L $failed ]]; then mv -T -- "$failed" "$live" || true; fi
    return 1
  fi
}

self_test() {
  local test_root live staged previous failed
  test_root=$(mktemp -d "${TMPDIR:-/tmp}/central-update-test.XXXXXX")
  trap 'rm -rf -- "$test_root"' RETURN

  live=$test_root/live
  staged=$test_root/staged
  previous=$test_root/previous
  failed=$test_root/failed
  mkdir -p "$live/central" "$staged/central" "$test_root/data"
  printf 'version anterior\n' >"$live/central/version.txt"
  printf 'version nueva\n' >"$staged/central/version.txt"
  printf 'aulas y datos intactos\n' >"$test_root/data/preserved.txt"

  switch_release "$live" "$staged" "$previous" ||
    fail "La prueba aislada no pudo activar la versión nueva."
  [[ $(cat "$live/central/version.txt") == 'version nueva' ]] ||
    fail "La prueba aislada no encontró la versión nueva."
  restore_release "$live" "$previous" "$failed" ||
    fail "La prueba aislada no pudo restaurar la versión anterior."
  [[ $(cat "$live/central/version.txt") == 'version anterior' &&
     $(cat "$failed/central/version.txt") == 'version nueva' &&
     $(cat "$test_root/data/preserved.txt") == 'aulas y datos intactos' ]] ||
    fail "La prueba aislada detectó un archivo perdido o una restauración incorrecta."

  mkdir -p "$test_root/private"
  php -r '
    $dbPath = $argv[1];
    $keyPath = dirname($dbPath) . "/.paypal-config.key";
    $db = new SQLite3($dbPath);
    $db->exec("CREATE TABLE schools(id INTEGER PRIMARY KEY)");
    $db->exec("CREATE TABLE users(id INTEGER PRIMARY KEY)");
    $db->exec("CREATE TABLE central_paypal_settings(id INTEGER PRIMARY KEY, encrypted_payload TEXT NOT NULL)");
    $db->exec("INSERT INTO schools VALUES(1)");
    $db->exec("INSERT INTO users VALUES(1)");
    $key = random_bytes(SODIUM_CRYPTO_SECRETBOX_KEYBYTES);
    file_put_contents($keyPath, $key);
    $nonce = random_bytes(SODIUM_CRYPTO_SECRETBOX_NONCEBYTES);
    $plain = json_encode(["client_id" => "self-test", "client_secret" => "self-test"], JSON_THROW_ON_ERROR);
    $packed = base64_encode($nonce . sodium_crypto_secretbox($plain, $nonce, $key));
    $stmt = $db->prepare("INSERT INTO central_paypal_settings VALUES(1, :payload)");
    $stmt->bindValue(":payload", $packed, SQLITE3_TEXT);
    $stmt->execute();
    $db->close();
    file_put_contents($argv[2], "<?php return " . var_export([
      "db_path" => $dbPath, "upload_dir" => dirname($dbPath), "base_url" => "https://example.test"
    ], true) . ";\n");
  ' "$test_root/private/live.sqlite3" "$test_root/private/config.php" ||
    fail "La prueba aislada no pudo crear SQLite de prueba."
  sqlite_backup "$test_root/private/live.sqlite3" "$test_root/private/backup.sqlite3" ||
    fail "La prueba aislada no pudo respaldar SQLite."
  validate_paypal_and_database "$test_root/private/live.sqlite3" \
    "$test_root/private/backup.sqlite3" "$test_root/private/config.php" ||
    fail "La copia SQLite aislada no pasó la validación de estructura o clave PayPal."
  printf 'Prueba aislada correcta: restauró el código anterior, verificó SQLite y PayPal, y no alteró los datos.\n'
}

php_config_values() {
  php -r '
    $c = require $argv[1];
    foreach (["db_path", "upload_dir", "base_url"] as $key) {
      if (!is_array($c) || !isset($c[$key]) || !is_string($c[$key]) ||
          $c[$key] === "" || preg_match("/[\t\r\n]/", $c[$key])) exit(2);
      echo $c[$key], "\t";
    }
  ' "$1"
}

validate_paypal_and_database() {
  local db_path=$1 backup_db=${2:-} config_path=${3:-$CONFIG_FILE}
  php -r '
    $config = require $argv[1];
    $dbPath = $argv[2];
    $backupPath = $argv[3] ?? "";
    $keyPath = dirname($dbPath) . "/.paypal-config.key";
    if (!extension_loaded("sqlite3") || !extension_loaded("sodium")) exit(10);
    if (!is_file($dbPath) || is_link($dbPath)) exit(11);
    $db = new SQLite3($dbPath, SQLITE3_OPEN_READONLY);
    if ($db->querySingle("PRAGMA integrity_check") !== "ok") exit(12);
    foreach (["schools", "users"] as $table) {
      if (!$db->querySingle("SELECT 1 FROM sqlite_master WHERE type=\"table\" AND name=\"" . $table . "\"")) exit(13);
    }
    $hasSettings = (bool)$db->querySingle(
      "SELECT 1 FROM sqlite_master WHERE type=\"table\" AND name=\"central_paypal_settings\""
    );
    $row = $hasSettings ? $db->querySingle(
      "SELECT encrypted_payload FROM central_paypal_settings WHERE id=1", true
    ) : false;
    if (is_file($keyPath) || $row) {
      if (is_link($keyPath) || !is_file($keyPath)) exit(14);
      $key = file_get_contents($keyPath);
      if (!is_string($key) || strlen($key) !== SODIUM_CRYPTO_SECRETBOX_KEYBYTES) exit(15);
      if ($row) {
        $packed = base64_decode((string)$row["encrypted_payload"], true);
        $nonceBytes = SODIUM_CRYPTO_SECRETBOX_NONCEBYTES;
        if (!is_string($packed) || strlen($packed) <= $nonceBytes) exit(16);
        $plain = sodium_crypto_secretbox_open(substr($packed, $nonceBytes), substr($packed, 0, $nonceBytes), $key);
        $credentials = is_string($plain) ? json_decode($plain, true) : null;
        if (!is_array($credentials) || !is_string($credentials["client_id"] ?? null) ||
            !is_string($credentials["client_secret"] ?? null) ||
            $credentials["client_id"] === "" || $credentials["client_secret"] === "") exit(17);
      }
    }
    if ($backupPath !== "") {
      if (!is_file($backupPath) || is_link($backupPath)) exit(18);
      $copy = new SQLite3($backupPath, SQLITE3_OPEN_READONLY);
      if ($copy->querySingle("PRAGMA integrity_check") !== "ok") exit(19);
      $counts = static function (SQLite3 $connection): array {
        $result = $connection->query(
          "SELECT name FROM sqlite_master WHERE type=\"table\" AND name NOT LIKE \"sqlite_%\" ORDER BY name"
        );
        $tables = [];
        while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
          $name = (string)$row["name"];
          $quoted = "\"" . str_replace("\"", "\"\"", $name) . "\"";
          $tables[$name] = (int)$connection->querySingle("SELECT COUNT(*) FROM " . $quoted);
        }
        return $tables;
      };
      if ($counts($db) !== $counts($copy)) exit(20);
      if (!$copy->querySingle("SELECT 1 FROM sqlite_master WHERE type=\"table\" AND name=\"schools\"") ||
          !$copy->querySingle("SELECT 1 FROM sqlite_master WHERE type=\"table\" AND name=\"users\"")) exit(21);
      $copy->close();
    }
    $db->close();
  ' "$config_path" "$db_path" "$backup_db"
}

sqlite_backup() {
  php -r '
    $source = new SQLite3($argv[1], SQLITE3_OPEN_READONLY);
    $target = new SQLite3($argv[2]);
    if (!$source->backup($target)) exit(1);
    if ($target->querySingle("PRAGMA integrity_check") !== "ok") exit(2);
    $target->close();
    $source->close();
  ' "$1" "$2"
}

verify_runtime() {
  local required_packages=(apache2 libapache2-mod-php php-cli php-sqlite3 php-zip php-mbstring php-curl)
  local package extension
  for package in "${required_packages[@]}"; do
    dpkg-query -W -f='${db:Status-Status}' "$package" 2>/dev/null |
      grep -qx installed || fail "Falta el paquete requerido $package. Instálelo y repita la actualización."
  done
  php -r 'exit(PHP_VERSION_ID >= 80200 ? 0 : 1)' ||
    fail "Se requiere PHP 8.2 o superior."
  for extension in pdo_sqlite sqlite3 zip mbstring fileinfo sodium curl; do
    php -r 'exit(extension_loaded($argv[1]) ? 0 : 1);' "$extension" ||
      fail "PHP no tiene habilitada la extensión requerida: $extension."
  done
  [[ $(. /etc/os-release; printf '%s:%s' "${ID:-}" "${VERSION_ID:-}") == ubuntu:24.04 ]] ||
    fail "La actualización automática solo admite Ubuntu Server 24.04."
  systemctl is-active --quiet apache2 || fail "Apache no está activo; no se cambia el código."
  [[ -f $SITE_FILE && ! -L $SITE_FILE && -L $SITE_ENABLED ]] ||
    fail "No encuentro el sitio conta-central habilitado en su ubicación esperada."
  [[ $(readlink -f "$SITE_ENABLED") == "$SITE_FILE" ]] ||
    fail "El sitio conta-central habilitado no apunta a su configuración esperada."
}

validate_paths_and_config() {
  local values
  [[ -d $INSTALL_ROOT && ! -L $INSTALL_ROOT &&
     -d $INSTALL_ROOT/central/cpanel && -f $INSTALL_ROOT/central/cpanel/api.php ]] ||
    fail "No encuentro una instalación de Central en $INSTALL_ROOT."
  [[ -f $CONFIG_FILE && ! -L $CONFIG_FILE && -O $CONFIG_FILE ]] ||
    fail "La configuración debe existir, no ser un enlace simbólico y pertenecer a root."
  find "$CONFIG_FILE" -maxdepth 0 -perm /022 -print -quit | grep -q . &&
    fail "La configuración no debe permitir escritura al grupo ni a otros usuarios."
  values=$(php_config_values "$CONFIG_FILE") ||
    fail "No se pudo validar la configuración privada de Central."
  IFS=$'\t' read -r DB_PATH UPLOAD_DIR BASE_URL <<<"$values"
  [[ $DB_PATH == /* && $UPLOAD_DIR == /* && $BASE_URL == https://* ]] ||
    fail "La configuración requiere rutas absolutas de datos y una dirección HTTPS."
  [[ -f $DB_PATH && ! -L $DB_PATH && -d $UPLOAD_DIR && ! -L $UPLOAD_DIR ]] ||
    fail "SQLite o la carpeta privada de paquetes no existen o son enlaces simbólicos."
  [[ $DB_PATH != "$INSTALL_ROOT/"* && $UPLOAD_DIR != "$INSTALL_ROOT/"* ]] ||
    fail "SQLite y los paquetes deben estar fuera del directorio del código."
  [[ ! -e $DB_PATH-wal || ! -L $DB_PATH-wal ]] ||
    fail "El archivo WAL de SQLite no puede ser un enlace simbólico."
  find "$UPLOAD_DIR" -type l -print -quit | grep -q . &&
    fail "La carpeta de paquetes contiene enlaces simbólicos; revise esa instalación manualmente."
  validate_paypal_and_database "$DB_PATH" ||
    fail "SQLite no pasa integrity_check, faltan tablas o la clave PayPal no descifra sus credenciales. No se cambió el código."
}

create_verified_backup() {
  local key_path
  mkdir -p "$BACKUP_ROOT"
  chmod 0700 /var/backups/conta-fp360 "$BACKUP_ROOT"
  BACKUP_DIR=$(mktemp -d "$BACKUP_ROOT/update-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX")
  chmod 0700 "$BACKUP_DIR"
  mkdir -m 0700 "$BACKUP_DIR/packages"
  cp -a -- "$CONFIG_FILE" "$BACKUP_DIR/config.php"
  chmod 0600 "$BACKUP_DIR/config.php"
  cp -a -- "$UPLOAD_DIR/." "$BACKUP_DIR/packages/"
  cp -- "$SCRIPT_DIR/update.sh" "$BACKUP_DIR/update.sh"
  chmod 0700 "$BACKUP_DIR/update.sh"

  sqlite_backup "$DB_PATH" "$BACKUP_DIR/conta-central.sqlite3" ||
    fail "No se pudo crear la copia consistente de SQLite."
  chmod 0600 "$BACKUP_DIR/conta-central.sqlite3"
  validate_paypal_and_database "$DB_PATH" "$BACKUP_DIR/conta-central.sqlite3" ||
    fail "La copia de SQLite no pasó la verificación de integridad y contenido."
  cmp -s "$CONFIG_FILE" "$BACKUP_DIR/config.php" ||
    fail "La copia de la configuración no coincide con el original."
  diff -qr --no-dereference "$UPLOAD_DIR" "$BACKUP_DIR/packages" >/dev/null ||
    fail "La copia de los paquetes privados no coincide con el original."

  key_path=$(dirname "$DB_PATH")/.paypal-config.key
  if [[ -e $key_path || -L $key_path ]]; then
    [[ -f $key_path && ! -L $key_path ]] ||
      fail "La clave privada de PayPal no es un archivo regular."
    cp -- "$key_path" "$BACKUP_DIR/.paypal-config.key"
    chmod 0600 "$BACKUP_DIR/.paypal-config.key"
    cmp -s "$key_path" "$BACKUP_DIR/.paypal-config.key" ||
      fail "La copia de la clave PayPal no coincide con el original."
  fi
  printf 'Copia verificada: %s (SQLite, configuración, paquetes%s).\n' \
    "$BACKUP_DIR" "$([[ -f $BACKUP_DIR/.paypal-config.key ]] && printf ', clave PayPal' || printf ', sin clave PayPal configurada')"
}

check_staged_code() {
  local file
  [[ -f $SOURCE_DIR/cpanel/api.php && -f $SOURCE_DIR/ubuntu/apache-central.conf &&
     -f $SCRIPT_DIR/update.sh ]] ||
    fail "El paquete nuevo no contiene el código completo de Central para Ubuntu."
  find "$SOURCE_DIR" -type l -print -quit | grep -q . &&
    fail "El código nuevo contiene enlaces simbólicos; no se instala."
  STAGE_ROOT=$(mktemp -d /var/www/.conta-fp360-stage.XXXXXX)
  mkdir -p "$STAGE_ROOT/central"
  cp -a -- "$SOURCE_DIR/." "$STAGE_ROOT/central/"
  chown -R root:root "$STAGE_ROOT"
  find "$STAGE_ROOT" -type d -exec chmod 0755 {} +
  find "$STAGE_ROOT" -type f -exec chmod 0644 {} +
  while IFS= read -r -d '' file; do
    php -l "$file" >/dev/null || fail "Error de sintaxis PHP en el código nuevo: $file"
  done < <(find "$STAGE_ROOT/central" -type f -name '*.php' -print0)
  [[ -f $STAGE_ROOT/central/cpanel/api.php &&
     ! -e $STAGE_ROOT/central/cpanel/config.php ]] ||
    fail "La versión preparada no es válida o incluye una configuración privada."
}

health_check() {
  php -r '
    $url = $argv[1];
    $parts = parse_url($url);
    if (!$parts || ($parts["scheme"] ?? "") !== "https" || empty($parts["host"])) exit(2);
    $base = rtrim($url, "/");
    $health = $base . "/api.php?r=health";
    $curl = curl_init($health);
    curl_setopt_array($curl, [
      CURLOPT_RETURNTRANSFER => true,
      CURLOPT_CONNECTTIMEOUT => 5,
      CURLOPT_TIMEOUT => 15,
      CURLOPT_SSL_VERIFYPEER => true,
      CURLOPT_SSL_VERIFYHOST => 2,
      CURLOPT_RESOLVE => [$parts["host"] . ":443:127.0.0.1"],
    ]);
    $body = curl_exec($curl);
    $status = (int)curl_getinfo($curl, CURLINFO_RESPONSE_CODE);
    curl_close($curl);
    if (!is_string($body) || $status !== 200) exit(3);
    $result = json_decode($body, true);
    if (!is_array($result) || ($result["ok"] ?? false) !== true ||
        ($result["initialized"] ?? false) !== true) exit(4);
  ' "$1"
}

write_backup_state() {
  local state=$1 previous=${2:-}
  printf 'STATE=%s\nPREVIOUS_RELEASE=%s\n' "$state" "$previous" >"$BACKUP_DIR/.state.tmp"
  chmod 0600 "$BACKUP_DIR/.state.tmp"
  mv -f -- "$BACKUP_DIR/.state.tmp" "$BACKUP_DIR/state"
}

restore_after_failure() {
  local status=$?
  trap - EXIT
  if ((SWITCHED)); then
    printf '\nFalló la validación posterior al cambio; se restaura el código anterior.\n' >&2
    if restore_release "$INSTALL_ROOT" "$PREVIOUS_ROOT" "$FAILED_ROOT"; then
      if apache2ctl configtest && systemctl reload apache2 && health_check "$BASE_URL"; then
        write_backup_state failed "$PREVIOUS_ROOT"
        printf 'Se restauró el código anterior. SQLite, paquetes y configuración no se restauraron ni modificaron.\n' >&2
      else
        printf 'ATENCIÓN: el código anterior está restaurado, pero Apache no superó su comprobación. Revise el servicio manualmente.\n' >&2
      fi
    else
      printf 'ATENCIÓN: la restauración automática no pudo completarse. Versiones conservadas en %s y %s.\n' \
        "$INSTALL_ROOT" "$PREVIOUS_ROOT" >&2
    fi
  fi
  [[ -z $STAGE_ROOT || ! -d $STAGE_ROOT ]] || rm -rf -- "$STAGE_ROOT"
  exit "$status"
}

rollback_latest() {
  local candidate state previous suffix failed_dir
  [[ $EUID -eq 0 ]] || fail "Ejecute la restauración como administrador: sudo /usr/local/sbin/conta-central-update --rollback"
  [[ -d $BACKUP_ROOT ]] || fail "No hay copias de actualización para restaurar."
  candidate=''
  while IFS= read -r dir; do
    [[ -f $dir/state ]] || continue
    state=$(sed -n 's/^STATE=//p' "$dir/state")
    if [[ $state == active ]]; then candidate=$dir; break; fi
  done < <(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name 'update-*' -print | sort -r)
  [[ -n $candidate ]] || fail "No hay una actualización satisfactoria pendiente de restauración."
  previous=$(sed -n 's/^PREVIOUS_RELEASE=//p' "$candidate/state")
  [[ $previous == /var/www/conta-fp360.previous.* && -d $previous && ! -L $previous ]] ||
    fail "No se encuentra la versión anterior registrada. No se cambia el código."
  [[ -d $INSTALL_ROOT && ! -L $INSTALL_ROOT ]] ||
    fail "No se encuentra la versión activa de Central."
  apache2ctl configtest || fail "Apache no supera configtest. No se cambia el código."
  suffix=$(date -u +%Y%m%dT%H%M%SZ)
  failed_dir=$INSTALL_ROOT.rolled-back.$suffix
  restore_release "$INSTALL_ROOT" "$previous" "$failed_dir" ||
    fail "No se pudo intercambiar el código; se conservaron ambas versiones."
  if ! apache2ctl configtest || ! systemctl reload apache2 || ! health_check "$BASE_URL"; then
    if restore_release "$INSTALL_ROOT" "$failed_dir" "$INSTALL_ROOT.rollback-failed.$suffix"; then
      apache2ctl configtest && systemctl reload apache2 || true
    fi
    fail "La versión anterior no superó la comprobación. Se restauró la versión que estaba activa; no se cambiaron los datos."
  fi
  BACKUP_DIR=$candidate
  write_backup_state rolled-back "$previous"
  printf 'Versión de código anterior restaurada correctamente.\nSQLite, paquetes privados y configuración permanecen en su estado actual.\n'
}

case "${1:-}" in
  --help|-h) usage; exit 0 ;;
  --self-test) self_test; exit 0 ;;
  --rollback)
    [[ $# -eq 1 ]] || fail "No se admiten argumentos adicionales con --rollback."
    mkdir -p /run/lock
    exec 9>"$LOCK_FILE"
    flock -n 9 || fail "Ya hay otra actualización o restauración en curso."
    [[ -f $CONFIG_FILE ]] || fail "No encuentro la configuración de Central."
    values=$(php_config_values "$CONFIG_FILE") || fail "No se pudo leer la configuración privada."
    IFS=$'\t' read -r DB_PATH UPLOAD_DIR BASE_URL <<<"$values"
    rollback_latest
    exit 0
    ;;
  '') ;;
  *) fail "Opción desconocida: $1. Use --help." ;;
esac

[[ $# -eq 0 ]] || fail "No se admiten argumentos adicionales. Use --help."
[[ $EUID -eq 0 ]] || fail "Ejecute la actualización como administrador: sudo bash central/ubuntu/update.sh"
[[ -f $SCRIPT_DIR/apache-central.conf && -f $SOURCE_DIR/cpanel/api.php ]] ||
  fail "Ejecute el actualizador desde el repositorio o el paquete oficial de Central."

mkdir -p /run/lock
exec 9>"$LOCK_FILE"
flock -n 9 || fail "Ya hay otra actualización o restauración en curso."
trap restore_after_failure EXIT

verify_runtime
validate_paths_and_config
create_verified_backup
check_staged_code
PREVIOUS_ROOT=$INSTALL_ROOT.previous.$(date -u +%Y%m%dT%H%M%SZ)
FAILED_ROOT=$INSTALL_ROOT.failed.$(date -u +%Y%m%dT%H%M%SZ)
[[ ! -e $PREVIOUS_ROOT && ! -L $PREVIOUS_ROOT &&
   ! -e $FAILED_ROOT && ! -L $FAILED_ROOT ]] ||
  fail "Ya existe una carpeta con el nombre de respaldo previsto; inténtelo de nuevo."

# Valida Apache antes de cambiar cualquier código en uso.
apache2ctl configtest || fail "Apache no supera configtest; no se cambia el código."
switch_release "$INSTALL_ROOT" "$STAGE_ROOT" "$PREVIOUS_ROOT" ||
  fail "No se pudo activar el código nuevo; el código anterior permanece disponible."
STAGE_ROOT=''
SWITCHED=1
apache2ctl configtest || fail "Apache no supera configtest después del cambio."
systemctl reload apache2 || fail "Apache no pudo recargar el código nuevo."
health_check "$BASE_URL" || fail "La comprobación HTTPS local de Central no pasó."
write_backup_state active "$PREVIOUS_ROOT"
trap - EXIT

if install -o root -g root -m 0750 "$SCRIPT_DIR/update.sh" /usr/local/sbin/conta-central-update.tmp; then
  mv -f -- /usr/local/sbin/conta-central-update.tmp /usr/local/sbin/conta-central-update
  printf 'Actualización completada. Restauración disponible con: sudo /usr/local/sbin/conta-central-update --rollback\n'
else
  rm -f -- /usr/local/sbin/conta-central-update.tmp
  printf 'Actualización completada. Si necesita restaurar, ejecute: sudo bash %s/update.sh --rollback\n' "$BACKUP_DIR"
fi
printf 'Versión anterior conservada en: %s\nCopia de datos verificada en: %s\n' "$PREVIOUS_ROOT" "$BACKUP_DIR"
