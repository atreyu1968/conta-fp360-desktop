# CONTA FP360 Desktop — v2.1

Dos aplicaciones independientes de contabilidad educativa para Windows 10 y Windows 11 (x64), construidas con **Tauri 2** y las interfaces originales de CONTA FP360 v2.1.

**Autor y titular:** Francisco Javier González Rolo. Reservados todos los derechos. No se concede licencia abierta de reutilización del código (UNLICENSED).

## Aplicaciones

- **CONTA FP360 Studio**: creación y validación de supuestos, documentación y exportaciones para profesorado.
- **CONTA FP360 Aula**: importación de paquetes docentes, práctica de asientos, consulta de documentos, balances e informes para alumnado.

Cada aplicación utiliza un identificador distinto y por tanto un almacenamiento local separado. El uso principal es **sin Internet**. El instalador de Windows incorpora WebView2 offline. Los enlaces externos y cualquier servicio opcional de inteligencia artificial sí necesitan conexión.

## Instaladores automáticos

En GitHub, abra **Actions → CONTA FP360 Desktop - instaladores Windows**. Se ejecuta al publicar cambios en main o manualmente. Si las verificaciones pasan, se generarán los artefactos:

- CONTA-FP360-Studio-Windows-x64
- CONTA-FP360-Aula-Windows-x64

Cada artefacto incluye un instalador EXE NSIS y un fichero SHA-256. Se construyen por separado en windows-2022. **No se considera verificada la compilación hasta que GitHub Actions termine correctamente**.

## Compilación manual

Instale Rust, Microsoft C++ Build Tools y Tauri CLI 2. Desde el directorio src-tauri ejecute:

    cargo install tauri-cli --version '^2' --locked
    cargo tauri build --bundles nsis
    cargo tauri build --config tauri.aula.conf.json --bundles nsis

Los instaladores aparecen en src-tauri/target/release/bundle/nsis. Los ejecutables no están firmados y Windows SmartScreen podría mostrar una advertencia.

## Arquitectura y seguridad

- web/studio/index.html y web/aula/index.html conservan los motores HTML/JavaScript de la versión 2.1.
- web/*/desktop-bridge.js adapta las descargas a un diálogo nativo, abre enlaces externos en el navegador predeterminado y adapta la impresión.
- src-tauri/src/lib.rs implementa un comando acotado de escritura de archivos solicitado por el usuario, con límite de 200 MB.
- src-tauri/tauri.conf.json y tauri.aula.conf.json definen identificadores y perfiles diferentes.
- No se incorpora un servidor de evaluación remota ni garantía de antifraude. **No distribuir el JSON maestro ni las soluciones docentes al alumnado.**
- El guardado usa localStorage/IndexedDB del perfil WebView2. Conviene exportar copias de seguridad antes de reinstalar, cambiar de equipo o limpiar datos.

## Pruebas

El flujo valida la estructura, comprueba la sintaxis del JavaScript y realiza pruebas de arranque y exportación simulada con Chromium. Estas pruebas **no sustituyen** las pruebas de WebView2 real en Windows: guardado de PDF/ZIP, impresión, reimportación, datos tras reinstalación, ejecución sin conexión y control del acceso a soluciones.

Se recomienda efectuar una revisión curricular y fiscal docente de los supuestos antes de utilizarlos con alumnado.

## Compatibilidad

Windows 10 y 11 x64. No se incluye Moodle LTI ni SCORM en estas dos aplicaciones Desktop.
