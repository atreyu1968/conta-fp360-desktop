# CONTA FP360

Código original importado de GitHub, no una recreación. La procedencia y rama
están documentadas en `IMPORTACION.md`; leerlo antes de actualizar desde remoto.

## Alcance acordado con el usuario

- Studio y Aula son las dos aplicaciones de escritorio: Linux, Windows y macOS.
- Central es el servidor web PHP/SQLite destinado a Ubuntu Server. No convertirlo
  en una tercera aplicación Tauri ni migrar su base de datos a PostgreSQL.
- Priorizar el funcionamiento en Ubuntu sin eliminar los otros destinos.
- Inspeccionar los scripts, dependencias y pruebas reales antes de afirmar
  compatibilidad. Diferenciar siempre CI, pruebas físicas y producción.
- Conservar el español en la interfaz y la documentación existente.
- En las aplicaciones de escritorio, el enlace del servidor debe configurarse
  manualmente.
- El usuario quiere vender el servicio a varios docentes mediante PayPal, por
  número de aulas y con caducidad anual. Las aplicaciones de escritorio deben
  vincularse con la cuenta del profesor concreto.
- La tarifa confirmada es de 10 € por aula y año.
- No hay soporte personalizado.
- PayPal se configura dentro del panel de Central, no mediante una conexión de
  Replit. Sus credenciales permanecen en el servidor, no en Studio/Aula.
- `PLAN_NEGOCIO.md` contiene una propuesta comercial pendiente de aprobación;
  están confirmadas la tarifa de 10 € por aula y año y la ausencia de soporte
  personalizado. Los demás límites y plazos no están confirmados ni activados.
- Firma/notarización macOS y despliegue real del servidor no se consideran
  comprobados por el mero hecho de añadir un workflow o compilar un paquete.

## Código y ejecución

- `web/{studio,aula}` y `src-tauri`: interfaces originales y escritorio Tauri.
- `central/cpanel`: servidor y panel PHP original, también reutilizado en Ubuntu.
- `central/ubuntu`: instalación CLI, Apache y router exclusivo de desarrollo.
- `UBUNTU_SERVER.md`: requisitos, permisos, HTTPS e instalación de Ubuntu Server.
- La vista local usa el servicio `Central PHP` del artefacto `api-server`. Sirve
  los PHP originales, sin reescribirlos en React/Express. Sin configurar una
  instalación privada, solo permite visualizar el acceso, no utilizar cuentas.
- El servidor integrado PHP no se configura como servidor de producción.

## Validaciones

Desde la raíz:

```bash
python3 tests/validate_project.py
python3 tests/check_embedded_scripts.py
python3 tests/test_release_manifest.py
python3 central/tests/check_schema.py
python3 central/tests/test_installer_http.py
python3 central/tests/test_cpanel_http.py
python3 central/tests/test_ubuntu_setup.py
python3 central/tests/test_ubuntu_http.py
python3 scripts/build_ubuntu_bundle.py
```

PHP requiere PDO SQLite, SQLite3, ZIP, mbstring y fileinfo. Las pruebas HTTP crean
datos ficticios temporales, no utilizan usuarios ni servidores de producción.
El test visual original necesita Playwright y Chromium; admite
`CHROMIUM_EXECUTABLE` para un navegador del sistema. Los demás smoke tests de
escritorio usan por defecto el Chromium instalado por Playwright en CI.

## Seguridad

`CONTA_CONFIG_FILE` permite configuración privada fuera del DocumentRoot y cierra
el instalador HTTP incluso si falta el fichero. cPanel conserva su ruta original
si no se establece esa variable. No guardar contraseñas o datos personales en
Git, ni introducirlos en argumentos CLI. Generados en `generated-artifacts/`,
excluido de Git y despliegues. Consultar `VALIDACION.md` para los límites de las
comprobaciones realizadas.
