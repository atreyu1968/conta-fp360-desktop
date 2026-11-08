#!/usr/bin/env bash
# Instalador guiado de Central para Ubuntu Server 24.04 LTS.
# No modifica instalaciones existentes ni maneja contraseñas en argumentos.
set -Eeuo pipefail
umask 077

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly SOURCE_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
readonly INSTALL_ROOT=/var/www/conta-fp360
readonly DATA_DIR=/var/lib/conta-fp360
readonly CONFIG_DIR=/etc/conta-fp360
readonly CONFIG_FILE=$CONFIG_DIR/config.php
readonly SITE_FILE=/etc/apache2/sites-available/conta-central.conf
readonly SITE_NAME=conta-central

DOMAIN=''
SCHOOL=''
ADMIN_NAME=''
ADMIN_EMAIL=''
CONTACT_EMAIL=''
CERT_FILE=''
KEY_FILE=''
USE_LETSENCRYPT=0
ADMIN_PASSWORD_STDIN=0
YES=0
DRY_RUN=0
TEMP_SITE=0
SITE_ENABLED=0
TEMP_ROOT=''
TLS_TEMP_DIR=''
PASSWORD=''

fail() { printf 'Error: %s\n' "$*" >&2; exit 1; }
cleanup_tls_temp() {
  if [[ -n $TLS_TEMP_DIR && -d $TLS_TEMP_DIR ]]; then
    rm -rf -- "$TLS_TEMP_DIR"
    TLS_TEMP_DIR=''
  fi
}
trap cleanup_tls_temp EXIT
usage() {
  cat <<'EOF'
Instalador guiado de CONTA FP360 Central para Ubuntu Server 24.04.

Uso interactivo:
  sudo bash central/ubuntu/install.sh

Con certificado TLS ya instalado:
  sudo bash central/ubuntu/install.sh \
    --domain=central.ejemplo.org --certificate=/ruta/fullchain.pem \
    --private-key=/ruta/privkey.pem

Obtener un certificado Let's Encrypt nuevo (requiere DNS y puerto 80 accesibles):
  sudo bash central/ubuntu/install.sh \
    --domain=central.ejemplo.org --letsencrypt

Opciones:
  --school=NOMBRE              Centro educativo
  --name=NOMBRE                Nombre del administrador general
  --email=CORREO               Correo de la cuenta administradora
  --contact-email=CORREO       Correo de Let's Encrypt (por defecto, --email)
  --certificate=RUTA           Certificado TLS existente
  --private-key=RUTA           Clave privada del certificado existente
  --letsencrypt                Solicita un certificado válido a Let's Encrypt
  --admin-password-stdin       Lee la contraseña desde la entrada estándar
  --yes                        Confirma la instalación tras mostrar el resumen
  --dry-run                    Valida y muestra el plan; no cambia el sistema
  --help                       Muestra esta ayuda

No se acepta una contraseña como argumento, variable de entorno ni archivo del
repositorio. En modo interactivo se solicita sin mostrarla; en automatización
segura, envíela por entrada estándar con --admin-password-stdin.

Este instalador es solo para instalaciones nuevas. Para actualizar Central,
use el actualizador independiente central/ubuntu/update.sh.
EOF
}

while (($#)); do
  case "$1" in
    --domain=*) DOMAIN=${1#*=} ;;
    --school=*) SCHOOL=${1#*=} ;;
    --name=*) ADMIN_NAME=${1#*=} ;;
    --email=*) ADMIN_EMAIL=${1#*=} ;;
    --contact-email=*) CONTACT_EMAIL=${1#*=} ;;
    --certificate=*) CERT_FILE=${1#*=} ;;
    --private-key=*) KEY_FILE=${1#*=} ;;
    --letsencrypt) USE_LETSENCRYPT=1 ;;
    --admin-password-stdin) ADMIN_PASSWORD_STDIN=1 ;;
    --yes|-y) YES=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --help|-h) usage; exit 0 ;;
    *) fail "Opción desconocida: $1. Use --help." ;;
  esac
  shift
done

valid_domain() {
  local domain=$1 label
  [[ ${#domain} -le 253 && $domain == *.* ]] || return 1
  [[ ! $domain =~ ^[0-9.]+$ ]] || return 1
  IFS='.' read -r -a labels <<<"$domain"
  for label in "${labels[@]}"; do
    [[ ${#label} -ge 1 && ${#label} -le 63 ]] || return 1
    [[ $label =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$ ]] || return 1
  done
  [[ ${labels[-1]} =~ ^[a-z][a-z-]+$ ]]
}

ask() {
  local variable=$1 prompt=$2 current=${!1}
  [[ -n $current ]] && return
  [[ -t 0 ]] || fail "Falta $variable. Indíquelo en la línea de comandos o ejecute el instalador en una terminal."
  read -r -p "$prompt: " current
  [[ -n $current ]] || fail "El campo $variable no puede estar vacío."
  printf -v "$variable" '%s' "$current"
}

sed_replacement() {
  local value=$1
  value=${value//\\/\\\\}
  value=${value//&/\\&}
  value=${value//|/\\|}
  printf '%s' "$value"
}

[[ -f "$SOURCE_DIR/cpanel/index.php" && -f "$SCRIPT_DIR/setup.php" &&
   -f "$SCRIPT_DIR/apache-central.conf" ]] ||
  fail "No encuentro Central completo junto a este instalador. Ejecútelo desde el repositorio o desde su paquete oficial."
if find "$SOURCE_DIR" -type l -print -quit | grep -q .; then
  fail "El código contiene enlaces simbólicos; revíselos antes de instalar."
fi
if ((!DRY_RUN && EUID != 0)); then
  fail "Ejecute el instalador como administrador: sudo bash central/ubuntu/install.sh"
fi

if [[ -n $DOMAIN ]]; then DOMAIN=${DOMAIN,,}; fi
ask DOMAIN "Dominio exclusivo de Central (ejemplo: central.ejemplo.org)"
valid_domain "$DOMAIN" || fail "Dominio no válido. Use un nombre DNS público, no una IP ni una dirección de correo."
ask SCHOOL "Nombre del centro educativo"
ask ADMIN_NAME "Nombre del administrador general"
ask ADMIN_EMAIL "Correo del administrador general"
[[ $ADMIN_EMAIL =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]] ||
  fail "El correo del administrador no parece válido."

if ((USE_LETSENCRYPT)); then
  [[ -z $CERT_FILE && -z $KEY_FILE ]] ||
    fail "Elija Let's Encrypt o un certificado existente; no ambas opciones."
  [[ -n $CONTACT_EMAIL ]] || CONTACT_EMAIL=$ADMIN_EMAIL
  [[ $CONTACT_EMAIL =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]] ||
    fail "El correo de contacto de Let's Encrypt no parece válido."
elif [[ -z $CERT_FILE && -z $KEY_FILE && -t 0 ]]; then
  printf '\nCentral necesita HTTPS para recibir credenciales.\n'
  read -r -p "¿Solicitar automáticamente un certificado público a Let's Encrypt? [s/N] " reply
  case "${reply,,}" in s|sí|si|y|yes) USE_LETSENCRYPT=1 ;;
    *) read -r -p "Ruta absoluta del certificado (fullchain.pem): " CERT_FILE
       read -r -p "Ruta absoluta de su clave privada (privkey.pem): " KEY_FILE ;;
  esac
  if ((USE_LETSENCRYPT)); then
    [[ -n $CONTACT_EMAIL ]] || CONTACT_EMAIL=$ADMIN_EMAIL
  fi
fi

if ((!USE_LETSENCRYPT)); then
  [[ -n $CERT_FILE && -n $KEY_FILE ]] ||
    fail "Se requiere HTTPS: proporcione --certificate y --private-key, o elija --letsencrypt."
  [[ $CERT_FILE == /* && $KEY_FILE == /* && -f $CERT_FILE && -f $KEY_FILE &&
     ! -L $CERT_FILE && ! -L $KEY_FILE && -r $CERT_FILE && -r $KEY_FILE ]] ||
    fail "El certificado y la clave TLS deben ser archivos absolutos, legibles y no enlaces simbólicos."
  openssl x509 -in "$CERT_FILE" -noout -checkhost "$DOMAIN" >/dev/null 2>&1 ||
    fail "El certificado no corresponde al dominio $DOMAIN."
  openssl x509 -in "$CERT_FILE" -noout -checkend 86400 >/dev/null 2>&1 ||
    fail "El certificado vence en menos de 24 horas o ya ha caducado."
  TLS_TEMP_DIR=$(mktemp -d /tmp/conta-fp360-tls.XXXXXX)
  leaf_cert=$TLS_TEMP_DIR/leaf.pem
  chain_certs=$TLS_TEMP_DIR/chain.pem
  openssl x509 -in "$CERT_FILE" -out "$leaf_cert" 2>/dev/null ||
    fail "No se pudo leer el certificado TLS."
  awk '/-----BEGIN CERTIFICATE-----/ { count++ } count>=2 { print }' "$CERT_FILE" >"$chain_certs"
  if [[ -s $chain_certs ]]; then
    openssl verify -CApath /etc/ssl/certs -purpose sslserver -verify_hostname "$DOMAIN" \
      -untrusted "$chain_certs" "$leaf_cert" >/dev/null 2>&1 ||
      fail "El certificado TLS no tiene una cadena de confianza válida para este servidor."
  else
    openssl verify -CApath /etc/ssl/certs -purpose sslserver -verify_hostname "$DOMAIN" \
      "$leaf_cert" >/dev/null 2>&1 ||
      fail "El certificado TLS no está emitido por una autoridad de confianza del servidor."
  fi
  cleanup_tls_temp
  openssl pkey -in "$KEY_FILE" -passin pass: -noout >/dev/null 2>&1 ||
    fail "La clave TLS no es válida o requiere contraseña. Apache necesita una clave sin frase de paso, protegida por permisos del sistema."
  cert_public=$(openssl x509 -in "$CERT_FILE" -pubkey -noout 2>/dev/null |
    openssl pkey -pubin -outform DER 2>/dev/null | sha256sum | cut -d' ' -f1)
  key_public=$(openssl pkey -in "$KEY_FILE" -pubout -outform DER 2>/dev/null |
    sha256sum | cut -d' ' -f1)
  [[ -n $cert_public && $cert_public == "$key_public" ]] ||
    fail "El certificado no corresponde a la clave privada indicada."
elif ((!DRY_RUN)) && [[ -e /etc/letsencrypt/live/$DOMAIN || -L /etc/letsencrypt/live/$DOMAIN ]]; then
  fail "Ya existe un certificado Let's Encrypt para $DOMAIN. No se sobrescribirá."
fi

if ((DRY_RUN)); then
  PASSWORD='Solo-validacion-local;no-se-usara'
elif ((ADMIN_PASSWORD_STDIN)); then
  IFS= read -r PASSWORD || fail "No se recibió la contraseña por la entrada estándar."
else
  [[ -t 0 ]] || fail "Para automatizar, use --admin-password-stdin; no pase contraseñas como argumento."
  read -r -s -p "Contraseña inicial del administrador (12–500 caracteres): " PASSWORD
  printf '\n'
  read -r -s -p "Repita la contraseña: " password_confirmation
  printf '\n'
  [[ $PASSWORD == "$password_confirmation" ]] || fail "Las contraseñas no coinciden."
  unset password_confirmation
fi
[[ ${#PASSWORD} -ge 12 && ${#PASSWORD} -le 500 && $PASSWORD != *$'\n'* ]] ||
  fail "La contraseña debe tener entre 12 y 500 caracteres."

if ((DRY_RUN)); then
  cat <<EOF
Comprobación correcta; no se ha instalado nada.
Dominio: $DOMAIN
Centro: $SCHOOL
Administrador: $ADMIN_EMAIL
Código: $SOURCE_DIR
Destino web: $INSTALL_ROOT
Datos privados: $DATA_DIR
Configuración: $CONFIG_FILE
Sitio Apache: $SITE_FILE
HTTPS: $([[ $USE_LETSENCRYPT == 1 ]] && echo "Let's Encrypt (solo se solicitará al ejecutar la instalación)" || echo "certificado existente validado")
Al ejecutar: instalar paquetes, preparar Central, crear SQLite y administrador,
configurar Apache HTTPS y recargar Apache. Los sitios y datos preexistentes no se sobrescriben.
EOF
  unset PASSWORD
  exit 0
fi

. /etc/os-release
[[ ${ID:-} == ubuntu && ${VERSION_ID:-} == 24.04 ]] ||
  fail "Instalación automática admitida en Ubuntu Server 24.04 LTS; no cambio otros sistemas."

for target in "$INSTALL_ROOT" "$DATA_DIR" "$CONFIG_DIR" "$SITE_FILE"; do
  [[ ! -e $target && ! -L $target ]] ||
    fail "Ya existe $target. No se sobrescriben instalaciones, datos ni sitios anteriores."
done
if ((USE_LETSENCRYPT)) && [[ -e /etc/letsencrypt/live/$DOMAIN || -L /etc/letsencrypt/live/$DOMAIN ]]; then
  fail "Ya existe un certificado Let's Encrypt para $DOMAIN. No se sobrescribirá."
fi

cat <<EOF

Se va a preparar una instalación nueva de Central:
  Ubuntu Server:             24.04
  Dominio:                   $DOMAIN
  Código:                    $INSTALL_ROOT
  SQLite y paquetes privados: $DATA_DIR
  Configuración privada:     $CONFIG_FILE
  Sitio Apache nuevo:        $SITE_FILE
  HTTPS:                     $([[ $USE_LETSENCRYPT == 1 ]] && echo "Let's Encrypt para $DOMAIN" || echo "certificado validado para $DOMAIN")

Se instalarán los paquetes necesarios de Apache y PHP. Apache podría recargarse.
No se modifica el firewall, no se deshabilitan sitios existentes y no se borran
datos ni configuraciones preexistentes.
EOF
if ((!YES)); then
  [[ -t 0 ]] || fail "La confirmación requiere terminal. Revise el plan y use --yes para automatizar conscientemente."
  read -r -p "¿Continuar con esta instalación nueva? [s/N] " reply
  case "${reply,,}" in s|sí|si|y|yes) ;; *) fail "Instalación cancelada; no se han instalado paquetes." ;; esac
fi

packages=(apache2 libapache2-mod-php php-cli php-sqlite3 php-zip php-mbstring php-curl)
if ((USE_LETSENCRYPT)); then packages+=(certbot); fi
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-upgrade "${packages[@]}"
unset DEBIAN_FRONTEND

for ext in pdo_sqlite sqlite3 zip mbstring fileinfo sodium curl; do
  php -r 'exit(extension_loaded($argv[1]) ? 0 : 1);' "$ext" ||
    fail "PHP no tiene habilitada la extensión requerida: $ext."
done

if apache2ctl -S 2>&1 | grep -Fq -- "$DOMAIN"; then
  fail "Apache ya tiene un sitio para $DOMAIN. Revíselo manualmente; no se modifica."
fi
if systemctl is-active --quiet apache2 && [[ $(apache2ctl -M 2>/dev/null) == *mpm_event_module* ]]; then
  fail "Apache ya usa MPM event. Para no afectar otros sitios, revise el módulo mod_php antes de continuar."
fi

temp_parent=$(mktemp -d /var/www/.conta-fp360-stage.XXXXXX)
TEMP_ROOT=$temp_parent
trap 'status=$?; if ((status!=0)); then
  if ((SITE_ENABLED)); then a2dissite "$SITE_NAME" >/dev/null 2>&1 || true; fi
  if ((SITE_ENABLED||TEMP_SITE)); then rm -f -- "$SITE_FILE"; fi
  if ((SITE_ENABLED||TEMP_SITE)); then apache2ctl configtest >/dev/null 2>&1 && systemctl reload apache2 >/dev/null 2>&1 || true; fi
  printf "\nLa instalación no finalizó. Se conservan los datos y configuración que ya se hayan creado para evitar pérdidas; revise %s y repare el paso indicado.\n" "$DATA_DIR" >&2
fi
cleanup_tls_temp
if [[ -n ${TEMP_ROOT:-} && -d $TEMP_ROOT ]]; then rm -rf -- "$TEMP_ROOT"; fi
exit "$status"' EXIT

mkdir -p "$temp_parent/central"
cp -a "$SOURCE_DIR/." "$temp_parent/central/"
install -d -o root -g root -m 0755 /var/www
mv -T -- "$temp_parent" "$INSTALL_ROOT"
TEMP_ROOT=''
chown -R root:root "$INSTALL_ROOT"
find "$INSTALL_ROOT" -type d -exec chmod 0755 {} +
find "$INSTALL_ROOT" -type f -exec chmod 0644 {} +

printf '%s\n' "$PASSWORD" | php "$INSTALL_ROOT/central/ubuntu/setup.php" \
  --config="$CONFIG_FILE" --data-dir="$DATA_DIR" --base-url="https://$DOMAIN" \
  --school="$SCHOOL" --name="$ADMIN_NAME" --email="$ADMIN_EMAIL" --password-stdin
unset PASSWORD
chown root:www-data "$CONFIG_DIR" "$CONFIG_FILE"
chmod 0750 "$CONFIG_DIR"
chmod 0640 "$CONFIG_FILE"
chown -R www-data:www-data "$DATA_DIR"
chmod 0700 "$DATA_DIR" "$DATA_DIR/packages"
chmod 0600 "$DATA_DIR/conta-central.sqlite3"

a2enmod ssl headers env setenvif >/dev/null
mkdir -p "$INSTALL_ROOT/central/cpanel/.well-known/acme-challenge"
chown -R root:root "$INSTALL_ROOT/central/cpanel/.well-known"
find "$INSTALL_ROOT/central/cpanel/.well-known" -type d -exec chmod 0755 {} +
find "$INSTALL_ROOT/central/cpanel/.well-known" -type f -exec chmod 0644 {} +

if ((USE_LETSENCRYPT)); then
  cat >"$SITE_FILE" <<EOF
<VirtualHost *:80>
    ServerName $DOMAIN
    DocumentRoot $INSTALL_ROOT/central/cpanel
    <Directory $INSTALL_ROOT/central/cpanel>
        AllowOverride None
        Options -Indexes -Includes -ExecCGI
    </Directory>
    <Directory $INSTALL_ROOT/central/cpanel/.well-known/acme-challenge>
        AllowOverride None
        Options None
        Require all granted
    </Directory>
    <Directory $INSTALL_ROOT/central/cpanel>
        Require all denied
    </Directory>
    <Directory $INSTALL_ROOT/central/cpanel/.well-known/acme-challenge>
        Require all granted
    </Directory>
</VirtualHost>
EOF
  TEMP_SITE=1
  a2ensite "$SITE_NAME" >/dev/null
  SITE_ENABLED=1
  apache2ctl configtest
  systemctl reload apache2
  certbot certonly --webroot --webroot-path "$INSTALL_ROOT/central/cpanel" \
    --non-interactive --agree-tos --no-eff-email --email "$CONTACT_EMAIL" -d "$DOMAIN"
  CERT_FILE="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
  KEY_FILE="/etc/letsencrypt/live/$DOMAIN/privkey.pem"
  openssl x509 -in "$CERT_FILE" -noout -checkhost "$DOMAIN" >/dev/null
fi

temp_conf=$(mktemp /etc/apache2/sites-available/.conta-central.XXXXXX)
escaped_domain=$(sed_replacement "$DOMAIN")
escaped_cert=$(sed_replacement "$CERT_FILE")
escaped_key=$(sed_replacement "$KEY_FILE")
sed "s|conta.ejemplo.org|$escaped_domain|g" "$INSTALL_ROOT/central/ubuntu/apache-central.conf" >"$temp_conf"
if ((USE_LETSENCRYPT)); then
  CERT_FILE="/etc/letsencrypt/live/$DOMAIN/fullchain.pem"
  KEY_FILE="/etc/letsencrypt/live/$DOMAIN/privkey.pem"
fi
sed -i "s|/etc/letsencrypt/live/$DOMAIN/fullchain.pem|$escaped_cert|g;
        s|/etc/letsencrypt/live/$DOMAIN/privkey.pem|$escaped_key|g" "$temp_conf"
chmod 0644 "$temp_conf"
if ! ((USE_LETSENCRYPT)); then
  a2ensite "$SITE_NAME" >/dev/null
  SITE_ENABLED=1
fi
mv -f -- "$temp_conf" "$SITE_FILE"
TEMP_SITE=0
apache2ctl configtest
systemctl reload apache2
unset TEMP_SITE SITE_ENABLED
trap - EXIT

cat <<EOF

Central está instalado y Apache se ha recargado correctamente.
Dirección: https://$DOMAIN/
Administrador: $ADMIN_EMAIL
Configuración privada: $CONFIG_FILE
SQLite y paquetes: $DATA_DIR

La contraseña inicial no se muestra ni se conserva en este instalador.
En las aplicaciones Studio y Aula, introduzca manualmente https://$DOMAIN/.
No se ha abierto el firewall; configure su proveedor/firewall para permitir
HTTPS (443). Para Let's Encrypt también se necesita el puerto 80 accesible.
Conserve una copia protegida de SQLite, paquetes, configuración y certificados.
EOF
