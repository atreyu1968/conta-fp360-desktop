# Central en Ubuntu Server

Central sigue siendo una aplicación **web PHP/SQLite**, no una tercera aplicación
de escritorio. Studio y Aula mantienen su código Tauri para Linux, Windows y macOS.
Se reutilizan la API, esquema, panel y reglas de evaluación originales.

## Alcance y estado

- Destino preparado: **Ubuntu Server 24.04 LTS**, Apache 2.4 + módulo PHP 8.3,
  SQLite, ZIP, mbstring y fileinfo. El código requiere PHP 8.2+.
- Se añade instalación CLI sin contraseñas en argumentos, configuración privada
  externa y una plantilla Apache HTTPS. cPanel conserva su instalador existente.
- Las pruebas HTTP usan datos ficticios y PHP integrado, **no** un servidor de
  producción. La nueva acción `central-ubuntu.yml` también valida la sintaxis de
  Apache; su mera presencia no demuestra que se haya ejecutado.
- Ubuntu 22.04 con su PHP 8.1 predeterminado **no cumple** los requisitos. No se
  declara compatible hasta instalar PHP 8.2+ y repetir las pruebas.
- Ni estos cambios ni un CI correcto acreditan instalación física en Ubuntu,
  Windows o macOS; firma/notarización Apple y producción continúan pendientes.

## 1. Preparación del servidor

En una máquina de pruebas, mantenga inicialmente cerrados los puertos públicos.
Use un dominio propio y planifique HTTPS y copias antes de manejar datos reales.

```bash
sudo apt update
sudo apt install apache2 libapache2-mod-php php-cli php-sqlite3 php-zip php-mbstring
php -v
php -m | grep -Ei 'pdo_sqlite|sqlite3|zip|mbstring|fileinfo'
sudo install -d -m 0755 /var/www/conta-fp360
# Desde la raíz de este repositorio (o del ZIP de Central):
sudo cp -a central /var/www/conta-fp360/
sudo chown -R root:root /var/www/conta-fp360/central
sudo find /var/www/conta-fp360/central -type d -exec chmod 0755 {} +
sudo find /var/www/conta-fp360/central -type f -exec chmod 0644 {} +
```

No copie un `config.php` ni bases de otra instalación a la carpeta pública.
La actualización de un servidor ya instalado **no** se hace ejecutando de nuevo
el instalador. Use la ruta de actualización segura de la sección siguiente.
Las migraciones existentes de Central son aditivas.

## 2. Alta inicial por terminal

### Instalador guiado

Desde el repositorio completo o su paquete oficial, también puede iniciar el
instalador automático:

```bash
sudo bash central/ubuntu/install.sh
```

Solicita dominio, centro y administrador; la contraseña se introduce oculta,
con confirmación, y nunca en el historial del shell. Use un dominio exclusivo
para Central y un certificado que cubra ese dominio. El instalador solicita
certificado con Let's Encrypt solo si lo elige expresamente; esto contacta una
autoridad pública, requiere DNS correcto y el puerto 80 accesible. También puede
usar un certificado existente. No modifica el firewall.

La instalación automática está limitada a Ubuntu Server 24.04. Instala Apache y
PHP con sus módulos, copia el código, llama al mismo `setup.php` CLI, crea la
configuración y SQLite privadas y activa únicamente el sitio `conta-central`.
No sobrescribe `/var/www/conta-fp360`, `/var/lib/conta-fp360`,
`/etc/conta-fp360` ni la configuración de un sitio con nombre repetido.
Comprueba previamente el dominio, el certificado y los módulos Apache que puedan
afectar otros sitios. La instalación no abre puertos en el firewall.

Antes de ejecutar, puede revisar la configuración y el resumen sin modificar el
servidor:

```bash
bash central/ubuntu/install.sh --dry-run --letsencrypt \
  --domain=conta.ejemplo.org --school="Centro educativo" \
  --name="Administrador" --email=admin@ejemplo.org
```

Para solicitar Let's Encrypt sin preguntas interactivas, añada
`--contact-email=admin@ejemplo.org --yes` y organice de forma segura la entrada
de la contraseña con `--admin-password-stdin`. No escriba contraseñas en comandos,
argumentos, ficheros del repositorio ni variables de entorno.

El instalador detiene la instalación si detecta un destino previo. No se usa para
actualizar Central. Ante un error posterior a la creación de la cuenta, conserva
los datos privados para impedir pérdidas; revise las instrucciones que muestra
antes de reparar manualmente.

### Actualizar una instalación existente

La actualización tiene un script propio y no ejecuta `install.sh` ni `setup.php`.
Desde la raíz del repositorio o el paquete oficial extraído, ejecute:

```bash
sudo bash central/ubuntu/update.sh
```

Antes de cambiar el código, comprueba Ubuntu 24.04, los paquetes y módulos PHP,
la configuración privada, el estado íntegro de SQLite, la carpeta de paquetes y
la clave PayPal. Si hay credenciales PayPal configuradas, verifica que la clave
permite descifrarlas sin mostrar ni registrar las credenciales. Un error de
validación detiene la actualización.

Prepara la versión nueva en una carpeta temporal, valida la sintaxis PHP y
ejecuta `apache2ctl configtest` **antes** del cambio. Crea una copia privada y
verificada de SQLite mediante la API de copia de SQLite, además de la
configuración, los paquetes y la clave PayPal, cuando exista. Solo entonces
intercambia el directorio del código, vuelve a validar Apache, lo recarga y
comprueba el endpoint HTTPS local. No instala paquetes ni escribe directamente
en las aulas, SQLite, los ZIP, la configuración o las credenciales. Una versión
nueva puede aplicar sus migraciones aditivas de SQLite cuando se atiendan
peticiones posteriores; por eso la reversión de código no deshace cambios de
esquema.

Después de una actualización satisfactoria se puede volver a la versión de
código anterior con:

```bash
sudo /usr/local/sbin/conta-central-update --rollback
```

La restauración también valida Apache y la respuesta HTTPS. Mantiene la versión
nueva y la anterior en el servidor. La restauración **no revierte migraciones de
SQLite ni restaura copias de datos**: el actualizador no modifica esos datos; no
use una copia antigua de SQLite para deshacer una actualización sin una
restauración ensayada y una evaluación explícita de pérdida de cambios recientes.
Conserve protegidos el respaldo verificado y las carpetas de versiones hasta
haber aceptado la actualización.

Para probar la mecánica de cambio y restauración sin tocar el servidor:

```bash
bash central/ubuntu/update.sh --self-test
```

Esta prueba usa únicamente directorios temporales; no instala ni cambia una
instalación de Central.

### Instalación manual alternativa

Solo para una instalación nueva. Sustituya dominio, centro, nombre y correo:

```bash
sudo php /var/www/conta-fp360/central/ubuntu/setup.php \
  --base-url=https://conta.ejemplo.org \
  --school="Centro educativo" --name="Administrador" --email=admin@ejemplo.org
```

La contraseña se solicita **oculta y con confirmación**, no se pasa como argumento
ni se guarda en scripts. No hay credenciales de demostración. `--password-stdin`
está disponible para automatización segura; nunca incluya la contraseña literal
en el historial, un fichero público o un workflow.

El instalador crea `/etc/conta-fp360/config.php` y
`/var/lib/conta-fp360/{conta-central.sqlite3,packages/}` con permisos privados.
Se niega a sobrescribir configuraciones, SQLite o directorios de paquetes previos.
Por defecto se exige cargar el catálogo curricular verificado antes de publicar.

Después ajuste los permisos para Apache (usuario `www-data` en Ubuntu estándar):

```bash
sudo chown root:www-data /etc/conta-fp360 /etc/conta-fp360/config.php
sudo chmod 0750 /etc/conta-fp360
sudo chmod 0640 /etc/conta-fp360/config.php
sudo chown -R www-data:www-data /var/lib/conta-fp360
sudo chmod 0700 /var/lib/conta-fp360 /var/lib/conta-fp360/packages
sudo chmod 0600 /var/lib/conta-fp360/conta-central.sqlite3
```

Apache puede escribir los datos y el WAL, pero **no** el código ni su configuración.
No use `chmod 777`. Para varias instalaciones, use rutas y usuarios de servicio
distintos y los parámetros `--config` y `--data-dir`.

## 3. Apache y HTTPS

La plantilla `central/ubuntu/apache-central.conf` está preparada para **mod_php**,
no PHP-FPM. Antes de habilitarla:

1. Obtenga un certificado válido mediante su procedimiento ACME/Certbot habitual.
2. Sustituya `conta.ejemplo.org` y las dos rutas de certificado por las reales.
3. Mantenga el `DocumentRoot` limitado a `central/cpanel`, nunca al repositorio.
4. Compruebe los nombres/puertos de otros sitios: no sobrescriba sitios existentes.

```bash
sudo a2enmod ssl headers env setenvif
sudo cp central/ubuntu/apache-central.conf /etc/apache2/sites-available/conta-central.conf
sudoedit /etc/apache2/sites-available/conta-central.conf
sudo a2ensite conta-central
sudo apache2ctl configtest
# Solo si aparece Syntax OK:
sudo systemctl reload apache2
```

HTTP redirige a HTTPS. La configuración establece `CONTA_CONFIG_FILE`, permite solo
`index.php` y `api.php` como puntos de entrada PHP, bloquea el instalador y archivos
privados, transmite Authorization y fija el tamaño máximo de las peticiones.
La configuración externa ausente produce un error explícito; **no** se recurre a
otra configuración pública. No desactive la verificación TLS de Studio/Aula.

Compruebe desde fuera del servidor:

```bash
curl --fail https://conta.ejemplo.org/api.php?r=health
# Debe responder initialized:true
curl -I https://conta.ejemplo.org/install.php
curl -I https://conta.ejemplo.org/schema.sql
# Ambos deben responder 403, nunca el instalador ni el SQL.
```

Abra la dirección HTTPS, acceda con el administrador y realice el piloto del
apartado de aceptación de `central/README.md`. En Studio/Aula se configura esa
misma URL HTTPS. Central no se empaqueta mediante Tauri.

## 4. Pruebas locales y paquete

Desde la raíz, con PHP y las extensiones anteriores, Python 3 y Node.js:

```bash
find central -name '*.php' -print0 | xargs -0 -n1 php -l
python3 central/tests/check_schema.py
python3 central/tests/test_installer_http.py
python3 central/tests/test_cpanel_http.py
python3 central/tests/test_ubuntu_setup.py
python3 central/tests/test_ubuntu_recovery.py
python3 central/tests/test_ubuntu_http.py
python3 central/tests/test_auto_installer.py
python3 central/tests/test_ubuntu_update.py
python3 scripts/build_ubuntu_bundle.py
```

La última orden genera un ZIP de **fuentes** y SHA-256 en `generated-artifacts/`;
incluye los scripts de instalación y actualización; no es un DEB ni un servidor
instalado. No incluye configuraciones privadas, contraseñas, SQLite, paquetes de
alumnado ni instaladores de escritorio.

`central/ubuntu/dev-router.php` permite una vista local mediante `php -S`, pero
el servidor integrado de PHP es **solo de desarrollo**, no de producción.
La interfaz se puede visualizar sin configuración; acceder a datos requiere una
instalación privada válida. No se abre un asistente público para crear administradores.

## 5. Copias y recuperación

Antes de producción: pruebe roles y separación entre centros, publique desde
Studio, descargue en Aula, trabaje offline, sincronice una entrega y valide sus
notas. Verifique reinicio del servicio, permisos, TLS, carga y restauración.

La herramienta `central/ubuntu/recovery.py` crea un archivo comprimido privado con
configuración, una instantánea consistente de SQLite, todos los paquetes y
`.paypal-config.key` si existe. Verifica integridad de SQLite, manifiesto y
permisos, y comprueba que la clave recuperada descifra la configuración de PayPal.
Si hay credenciales PayPal cifradas y falta la clave, la copia se cancela.

### Programar copias cifradas fuera del servidor

`central/ubuntu/offsite_backup.py` automatiza la copia, la cifra con `age` antes
de transferirla y la verifica en un segundo servidor por SSH/`rsync`. Instale las
herramientas:

```bash
sudo apt update
sudo apt install age rsync openssh-client
```

Genere la identidad `age` en un equipo o medio seguro que no sea el servidor
Central. Conserve allí el archivo privado; Central solo recibe la clave pública
`age1...`:

```bash
age-keygen -o /ruta-segura/central-age-identity.txt
grep '^# public key:' /ruta-segura/central-age-identity.txt
```

Configure autenticación SSH por clave para una cuenta dedicada de almacenamiento
externo y verifique manualmente la huella SSH del servidor remoto. Limite esa
cuenta al directorio de copias; necesita escribir, verificar y eliminar copias
vencidas según la retención. Mantenga el directorio remoto previamente creado,
propiedad de esa cuenta y sin acceso público. Proteja la clave SSH privada de
Central con permisos `0600`; esta clave de transporte no sustituye la identidad
privada `age`, que nunca debe copiarse al servidor.

Prepare el directorio local privado y ejecute una vez a mano para validar el
acceso SSH, la clave pública y el almacenamiento remoto:

```bash
sudo install -d -o root -g root -m 0700 /var/backups/conta-fp360/offsite
sudo python3 /var/www/conta-fp360/central/ubuntu/offsite_backup.py \
  --config=/etc/conta-fp360/config.php \
  --data-dir=/var/lib/conta-fp360 \
  --local-dir=/var/backups/conta-fp360/offsite \
  --recipient=age1CLAVE_PUBLICA_DEL_CENTRO \
  --ssh-target=backup@copias.ejemplo.org \
  --remote-dir=/srv/copias/conta-fp360 \
  --retention-days=35
```

El proceso detiene Apache solo mientras obtiene la instantánea consistente,
intenta iniciarlo de nuevo incluso si falla la copia y después cifra y transfiere
el archivo. El servidor recibe únicamente `.tar.gz.age` y su suma SHA-256. La
transferencia se verifica en el destino antes de aplicar retención. Si falta una
herramienta, falla SSH, no coincide la suma o no se puede iniciar Apache, el
comando termina con error; revise `sudo journalctl -u conta-fp360-backup.service`.

Para programarlo cada día a las 02:30 UTC, cree el servicio
`/etc/systemd/system/conta-fp360-backup.service`, sustituyendo la clave pública
por la real:

```ini
[Unit]
Description=Copia cifrada externa de CONTA FP360 Central

[Service]
Type=oneshot
UMask=0077
ExecStart=/usr/bin/python3 /var/www/conta-fp360/central/ubuntu/offsite_backup.py --config=/etc/conta-fp360/config.php --data-dir=/var/lib/conta-fp360 --local-dir=/var/backups/conta-fp360/offsite --recipient=age1CLAVE_PUBLICA_DEL_CENTRO --ssh-target=backup@copias.ejemplo.org --remote-dir=/srv/copias/conta-fp360 --retention-days=35
```

Cree `/etc/systemd/system/conta-fp360-backup.timer`:

```ini
[Unit]
Description=Programa diario de copias externas de Central

[Timer]
OnCalendar=*-*-* 02:30:00 UTC
Persistent=true
RandomizedDelaySec=10m

[Install]
WantedBy=timers.target
```

Active y compruebe el temporizador:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now conta-fp360-backup.timer
systemctl list-timers conta-fp360-backup.timer
sudo systemctl start conta-fp360-backup.service
sudo systemctl status conta-fp360-backup.service
```

La retención predeterminada conserva 35 días. El borrado remoto usa la fecha UTC
del nombre `central-AAAAMMDDTHHMMSSZ.tar.gz.age`, y elimina solo archivos regulares
con ese formato que ya superaron el plazo, junto con su archivo `.sha256` regular.
No elimina directorios, enlaces, nombres no reconocidos ni copias dentro del
plazo. Cambie `--retention-days` únicamente si la política aprobada por el centro
lo requiere. Compruebe periódicamente que el temporizador terminó sin error y
que el destino conserva copias recientes.

### Probar una copia cifrada transferida

Al menos trimestralmente y después de cambiar la configuración, descargue una
copia remota a un equipo de recuperación autorizado. Necesita la identidad
privada `age` protegida fuera del servidor; no la deje en Central. Descargue el
archivo y la suma a la misma carpeta, sustituyendo el nombre por uno existente:

```bash
mkdir -m 0700 /tmp/central-restore-drill
cd /tmp/central-restore-drill
rsync -av backup@copias.ejemplo.org:/srv/copias/conta-fp360/central-AAAAMMDDTHHMMSSZ.tar.gz.age .
rsync -av backup@copias.ejemplo.org:/srv/copias/conta-fp360/central-AAAAMMDDTHHMMSSZ.tar.gz.age.sha256 .
sha256sum -c central-AAAAMMDDTHHMMSSZ.tar.gz.age.sha256
age --decrypt --identity /ruta-segura/central-age-identity.txt \
  --output=central-restaurada.tar.gz \
  central-AAAAMMDDTHHMMSSZ.tar.gz.age
sudo install -d -o root -g root -m 0700 /etc/conta-fp360-recovery
sudo python3 /var/www/conta-fp360/central/ubuntu/recovery.py restore \
  --archive=/tmp/central-restore-drill/central-restaurada.tar.gz \
  --config=/etc/conta-fp360-recovery/config.php \
  --data-dir=/var/lib/conta-fp360-recovery
sudo php -r '$c=require $argv[1]; $d=new PDO("sqlite:".$c["db_path"]); echo $d->query("PRAGMA integrity_check")->fetchColumn(), PHP_EOL;' \
  /etc/conta-fp360-recovery/config.php
```

La última comprobación debe imprimir `ok`. Confirme también que aparecen los
paquetes y, si se usa PayPal, la clave `.paypal-config.key`. Haga el ensayo en
rutas nuevas y aisladas, nunca encima de la instalación activa. Registre la fecha,
el nombre de la copia y el resultado del ensayo para poder confirmar que se
recupera una copia realmente transferida.

### Crear una copia

La copia incluye configuración, datos del centro y una clave de cifrado: trátela
como si contuviera credenciales. Use un disco o servicio de copias aprobado por el
centro, cifrado y con acceso restringido. Guarde además una copia fuera del
servidor y una suma SHA-256; no deje el único respaldo en el mismo disco.
El `tar.gz` creado directamente por `recovery.py backup` no tiene cifrado externo:
no lo transfiera ni lo almacene fuera de un área privada. Para copias externas
programadas, use el flujo con `offsite_backup.py` descrito arriba.
Detenga Apache durante la copia para que SQLite y los ZIP formen un único punto de
recuperación. Ejecute:

```bash
sudo systemctl stop apache2
sudo install -d -o root -g root -m 0700 /var/backups/conta-fp360
BACKUP="/var/backups/conta-fp360/central-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
sudo python3 /var/www/conta-fp360/central/ubuntu/recovery.py backup \
  --config=/etc/conta-fp360/config.php \
  --data-dir=/var/lib/conta-fp360 \
  --output="$BACKUP"
sudo systemctl start apache2
sudo sha256sum "$BACKUP" | sudo tee "$BACKUP.sha256" >/dev/null
sudo chmod 0600 "$BACKUP" "$BACKUP.sha256"
```

Compruebe que Apache haya vuelto a arrancar con `sudo systemctl status apache2`.
La salida de la copia indica que se validó SQLite y que la copia se creó. En una
instalación con rutas personalizadas, pase las rutas reales a `--config` y
`--data-dir`; SQLite y `packages/` deben estar dentro de ese directorio de datos.
El directorio donde se guarda el archivo debe existir y la copia no puede
sobrescribir un archivo anterior.

### Ensayar una restauración sin riesgo

Pruebe cada copia en rutas de ensayo nuevas, nunca encima de la instalación activa.
El comando se niega a utilizar una configuración o directorio de datos que ya
existan:

```bash
sudo install -d -o root -g root -m 0700 /etc/conta-fp360-recovery
sudo sha256sum -c /ruta/privada/central-AAAAMMDDTHHMMSSZ.tar.gz.sha256
sudo python3 /var/www/conta-fp360/central/ubuntu/recovery.py restore \
  --archive=/ruta/privada/central-AAAAMMDDTHHMMSSZ.tar.gz \
  --config=/etc/conta-fp360-recovery/config.php \
  --data-dir=/var/lib/conta-fp360-recovery
sudo php -r '$c=require $argv[1]; $d=new PDO("sqlite:".$c["db_path"]); echo $d->query("PRAGMA integrity_check")->fetchColumn(), PHP_EOL;' \
  /etc/conta-fp360-recovery/config.php
sudo find /var/lib/conta-fp360-recovery -maxdepth 2 -type f -printf '%m %p\n'
```

La comprobación debe imprimir `ok`. La lista debe contener SQLite, los paquetes
recuperados y, si PayPal estaba configurado, `.paypal-config.key`; todos deben
tener permisos privados. La restauración valida internamente que la clave sea
capaz de descifrar las credenciales guardadas. Puede comprobar después la conexión
desde **Administración → Configuración de PayPal → Comprobar conexión**; esa
comprobación valida credenciales con el entorno configurado y no realiza cobros.

### Recuperación después de un fallo

1. Prepare un Ubuntu compatible con las versiones de PHP y extensiones indicadas
   en esta guía. Instale y verifique `python3`; para PayPal, PHP necesita sodium.
2. Recupere el código Central desde el paquete de fuentes oficial y configure
   Apache/HTTPS. **No ejecute `setup.php` ni el instalador guiado como si fuera una
   instalación nueva:** generarían una base diferente. Mantenga Apache detenido.
3. Descifre la copia usando el procedimiento de custodia del centro. Compruebe la
   suma SHA-256 y restaure primero en las rutas de ensayo anteriores. No restaure
   una copia no verificada ni una clave PayPal por separado.
4. Si la prueba es correcta, confirme que las rutas de producción destino no
   existen. Si aún existen, no las sobrescriba: con Apache detenido, consérvelas
   con un nombre de cuarentena distinto y verifique el nombre antes de continuar.
   Luego restaure a `/etc/conta-fp360/config.php` y
   `/var/lib/conta-fp360`; el comando se detendrá si cualquiera ya existe.
5. Ajuste propietarios para Apache (`root:www-data` para la configuración y
   `www-data:www-data` para datos), aplique los permisos del apartado 2 y verifique
   `sudo apache2ctl configtest`. Inicie Apache solo después de confirmar el
   resultado `ok` de SQLite y la disponibilidad del código.
6. Compruebe HTTPS y `curl --fail https://conta.ejemplo.org/api.php?r=health`.
   Acceda con la cuenta administradora y compruebe un paquete y la configuración
   PayPal, si corresponde. No elimine la instalación en cuarentena hasta confirmar
   la recuperación y la política de retención del centro.

La configuración conserva la URL y los ajustes originales, pero la sesión de
administración no se recupera: inicie sesión con la cuenta de Central. Las
credenciales PayPal solo pueden descifrarse con el archivo original
`.paypal-config.key` de 32 bytes que se encuentra junto a SQLite; una clave nueva,
perdida o de otra instalación no sirve. Proteja conjuntamente la base y esa clave.
Si la copia no contiene clave, pero el servidor anterior aún responde, no cambie
ni reconfigure PayPal hasta haber hecho una copia recuperable. El restablecimiento
de la contraseña de administrador requiere un procedimiento aparte y no se hace
reinstalando sobre la base restaurada.

`python3 central/tests/test_ubuntu_recovery.py` ensaya en directorios temporales
una copia completa, restauración, descifrado PayPal, rechazo de archivos dañados
y bloqueo de sobrescritura; no toca rutas de sistema ni usa credenciales reales.
`python3 central/tests/test_ubuntu_offsite.py` usa una clave `age` de prueba,
simula el transporte SSH/`rsync`, comprueba la retención y restaura el archivo
cifrado que quedó en el destino simulado. Ambas pruebas usan datos ficticios y
no validan la instalación de producción. La custodia de la identidad privada
`age`, el acceso al almacenamiento remoto y el tratamiento de datos personales
siguen siendo responsabilidad del centro.

### Cambiar una contraseña de administrador olvidada

No ejecute el instalador para recuperar una cuenta: `setup.php` solo sirve para
instalaciones nuevas y no debe reemplazar SQLite. El comando separado de
recuperación cambia únicamente el hash de una cuenta administradora activa y
revoca sus sesiones vigentes. No modifica aulas, matrículas, otros usuarios,
paquetes, configuración ni credenciales PayPal.

Haga primero una copia recuperable y ejecute el comando desde una terminal del
servidor. Sustituya el correo por el de la cuenta administradora:

```bash
sudo python3 /var/www/conta-fp360/central/ubuntu/recovery.py reset-password \
  --config=/etc/conta-fp360/config.php \
  --email=admin@ejemplo.org
```

El programa solicita la contraseña dos veces sin mostrarla. Debe tener entre 12 y
500 caracteres. No se acepta una contraseña en argumentos, variables de entorno,
entrada redirigida ni archivos; así no queda en el historial del shell ni en los
registros del sistema. Si hay varias cuentas administradoras en una instalación,
indique el correo exacto de la cuenta activa que desea recuperar. El proceso usa
una transacción SQLite; si no encuentra esa cuenta, la contraseña no coincide con
las reglas o falla la escritura, no confirma el cambio. Las sesiones de esa cuenta
deberán volver a iniciar sesión.

Verifique SQLite y que siguen presentes los datos y archivos asociados:

```bash
sudo php -r '$c=require $argv[1]; $d=new PDO("sqlite:".$c["db_path"]); echo $d->query("PRAGMA integrity_check")->fetchColumn(), PHP_EOL;' \
  /etc/conta-fp360/config.php
sudo test -d /var/lib/conta-fp360/packages
sudo test -f /var/lib/conta-fp360/.paypal-config.key
```

La primera orden debe imprimir `ok`. La clave PayPal solo se comprueba si esta
instalación usa credenciales cifradas. Después inicie sesión con la contraseña
nueva y verifique un paquete y la conexión PayPal desde la administración, si
corresponde. No comparta la contraseña por correo ni la incluya en comandos.

`python3 central/tests/test_ubuntu_password_recovery.py` ensaya también en un
directorio temporal el cambio de hash, la revocación de sesiones y la preservación
de aulas, matrículas, paquetes, configuración y datos PayPal.
Esta prueba y las pruebas de copias anteriores usan datos ficticios y no validan
una instalación de producción. La custodia de la identidad privada `age`, el
acceso al almacenamiento remoto y el tratamiento de datos personales siguen
siendo responsabilidad del centro.
