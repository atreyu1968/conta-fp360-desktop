# CONTA FP360 Desktop para Linux (v2.1)

## Estado
Esta guía documenta la compilación y distribución de CONTA FP360 Studio y Aula para Linux x64 (amd64).
La configuración de CI reside en `.github/workflows/linux.yml`; **no considerar los paquetes publicados o verificados hasta obtener el resultado "success" de GitHub Actions** y comprobar los archivos en Artifacts.

## Versiones y privacidad
- **Studio** es exclusivo del profesorado; genera supuestos y soluciones.
- **Aula** está destinada al alumnado; importa los paquetes docentes sin incorporar el código o los archivos de solución del profesor.
- Mantener intactos los formatos existentes de intercambio JSON, ZIP y PDF.
- Ambos productos mantienen identificadores y almacenamiento local independientes.
- El funcionamiento principal es offline; posibles APIs de IA y enlaces externos requieren Internet.

## Paquetes generados
La acción compila `.deb` y `.AppImage` para cada edición en Ubuntu 22.04 x64:
- `CONTA-FP360-Studio-2.1.0-Linux-x64.deb`
- `CONTA-FP360-Studio-2.1.0-Linux-x64.AppImage`
- `CONTA-FP360-Aula-2.1.0-Linux-x64.deb`
- `CONTA-FP360-Aula-2.1.0-Linux-x64.AppImage`

Cada artefacto publicado también contiene `SHA256SUMS.txt`. Los nombres se materializan solo si la compilación termina correctamente.

## Instalación en Ubuntu / Debian / Linux Mint
1. Descargue el artefacto correspondiente en GitHub → Actions → «CONTA FP360 Desktop - paquetes Linux».
2. Extraiga el archivo ZIP del artefacto.
3. En el terminal, desde la carpeta descargada:
   ```bash
   sudo apt install ./CONTA-FP360-Studio-2.1.0-Linux-x64.deb
   # O, para el alumnado:
   sudo apt install ./CONTA-FP360-Aula-2.1.0-Linux-x64.deb
   ```
4. Inicie el programa desde el menú de aplicaciones del escritorio.

El paquete DEB deja que el gestor de paquetes resuelva las dependencias del sistema. La versión mínima de distribución concreta requiere pruebas reales. Ubuntu 22.04+ y Debian 12+ son referencias de construcción razonables por WebKitGTK 4.1, no una garantía exhaustiva.

## Ejecución sin instalar (AppImage)
```bash
chmod +x CONTA-FP360-Aula-2.1.0-Linux-x64.AppImage
./CONTA-FP360-Aula-2.1.0-Linux-x64.AppImage
```
Para el profesorado, sustituya `Aula` por `Studio`.
AppImage empaqueta numerosas dependencias, pero sigue dependiendo de compatibilidad con glibc y, en algunos equipos, componentes FUSE. No garantiza el funcionamiento en toda distribución Linux.

## Verificación de integridad
```bash
sha256sum -c SHA256SUMS.txt
```
Estos hashes protegen la **integridad** frente a alteraciones accidentales, pero no prueban la identidad del editor; más adelante se puede añadir firma GPG.

## Compilación manual (desarrolladores)
Se requieren Rust, Tauri CLI v2 y bibliotecas de compilación de WebKitGTK 4.1. En Ubuntu 22.04:
```bash
sudo apt update
sudo apt install libwebkit2gtk-4.1-dev build-essential curl wget file \
  libxdo-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev \
  libfuse2 pkg-config patchelf
npm install --global '@tauri-apps/cli@2'
cd src-tauri
tauri build --bundles deb,appimage
tauri build --config tauri.aula.conf.json --bundles deb,appimage
```

## Pruebas pendientes en equipos Linux reales
1. Apertura en GNOME/X11 y Wayland.
2. Registro y recuperación de asientos tras cerrar y reiniciar.
3. Importación del mismo ZIP generado en Windows.
4. Generación y guardado de PDF, ZIP, JSON; apertura mediante aplicaciones del sistema.
5. Impresión y vista previa en WebKitGTK.
6. Ejecución sin Internet y separación de datos Studio/Aula.
7. Comprobación de que no se empaqueten soluciones docentes en Aula.
8. Prueba de reinstalación, desinstalación, conservación de los datos del usuario.

## Soporte futuro
Se podrán añadir paquetes RPM (Fedora) y ARM64 en ejecuciones separadas cuando los paquetes x64 se hayan validado. No se han preparado en la primera fase.

Documentación oficial:
- https://v2.tauri.app/start/prerequisites/
- https://v2.tauri.app/distribute/debian/
- https://v2.tauri.app/distribute/appimage/
