# Comprobaciones realizadas

## Entorno local — 8 de noviembre de 2026

Se ejecutó el código importado y modificado en este entorno Linux **NixOS**, con
PHP 8.4.27 y sus extensiones PDO SQLite, SQLite3, ZIP, mbstring y fileinfo;
Python 3.13, Node.js 24 y Chromium. **No es un equipo Ubuntu Server real.**

### Comprobaciones satisfactorias

- Sintaxis de todos los PHP de `central` y JavaScript del panel.
- `central/tests/check_schema.py`: SQLite real, claves, roles e integridad.
- `central/tests/test_installer_http.py`: dos instalaciones HTTP, nueva y reparación,
  con la vía cPanel original y datos temporales.
- `central/tests/test_cpanel_http.py`: API HTTP real con PHP/SQLite/ZIP.
- `central/tests/test_ubuntu_setup.py`: instalación CLI, permisos privados,
  HTTPS obligatorio salvo loopback, no sobrescritura y bloqueo del instalador web.
- `central/tests/test_ubuntu_http.py`: API HTTP real con configuración y datos
  fuera del DocumentRoot, protección de archivos y catálogo curricular obligatorio.
- Ambos flujos HTTP cubren alta/cambio de contraseña, roles, grupos, paquetes ZIP,
  asignaciones, descargas, entregas tardías, idempotencia, notas 60/40, auditoría,
  políticas de evaluación, separación de centros y limitación de intentos de acceso.
- `tests/validate_project.py`, `tests/check_embedded_scripts.py` y
  `tests/test_release_manifest.py`: estructura, sintaxis, separación de ediciones
  y contratos de actualización de los escritorios.
- Los tres smoke tests originales de Chromium: `smoke_browser.py`,
  `smoke_central.py` y `smoke_visual_central.py`. Sus puentes nativos y API están
  **simulados**: no prueban Tauri/WebKitGTK/WebView2/WKWebView reales.
- El test visual comprueba también credenciales incorrectas visibles y reinicio
  del formulario de alta tras una respuesta. Se corrigió la exposición del menú
  antes de completar la carga inicial que reproducía el fallo de CI original.
- El paquete Ubuntu se construyó con comprobación CRC y SHA-256; dos compilaciones
  del mismo código produjeron ZIP idéntico. No incluye datos ni configuración privada.

Para Chromium del sistema, el test visual admite:

```bash
CHROMIUM_EXECUTABLE="$(command -v chromium)" python3 tests/smoke_visual_central.py
```

Los otros dos smoke tests se ejecutaron aquí con el mismo Chromium mediante un
adaptador de lanzamiento de Playwright; no se modificó su aplicación ni sus
aserciones. En CI utilizan el navegador instalado por Playwright 1.56.

## GitHub Actions del repositorio original

La consulta del 8 de noviembre de 2026 mostró:

- Linux, ejecución [42499926173](https://github.com/atreyu1968/conta-fp360-desktop/actions/runs/42499926173):
  `success` para el commit anterior `00fbd415663d` en la rama de consolidación.
  No acredita este código modificado ni su ejecución física en Ubuntu.
- Windows, ejecución [42500607953](https://github.com/atreyu1968/conta-fp360-desktop/actions/runs/42500607953):
  `failure` para el commit importado, en «Verificar interfaz web Central con
  Chromium». Los trabajos de instaladores quedaron omitidos. El test ya pasa
  localmente tras la corrección, pero **no se ha vuelto a ejecutar ese CI**.
- Se observaron ejecuciones anteriores satisfactorias de PHP/SQLite de Central.
  No equivalen a probar Apache o un alojamiento de producción.
- La rama contiene un workflow macOS Intel/Apple Silicon. **No se ha verificado
  una compilación ni firma/notarización macOS en esta sesión.**

La nueva acción `central-ubuntu.yml` está preparada para Ubuntu 24.04/PHP 8.3,
pruebas HTTP y `apache2ctl configtest` con un certificado ficticio. **Está pendiente
de ejecutarse en GitHub**: no se han subido cambios ni disparado workflows remotos.
El instalador guiado `central/ubuntu/install.sh` dispone de comprobación Bash y
modo `--dry-run`; estas verificaciones no instalan paquetes, no solicitan
certificados ACME y no equivalen a instalar en un Ubuntu Server real.

## Pendiente fuera de este entorno

- Compilación nativa del código actual de Studio/Aula en cada destino.
- Pruebas presenciales en Ubuntu X11/Wayland, Windows y macOS; impresión, PDF,
  migración, reinstalación y persistencia reales.
- Firma comercial de Windows y Apple Developer ID/notarización; actualizaciones
  firmadas probadas entre versiones.
- Apache/PHP del Ubuntu de destino, HTTPS real, copias y restauración,
  concurrencia y piloto con usuarios autorizados.
- Revisión institucional de protección de datos antes de usar datos de alumnado.

La vista local de Central muestra la interfaz original sin cuentas precreadas.
La instalación privada del servidor no se ha realizado en producción.
