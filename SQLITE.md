# CONTA FP360 Desktop 2.2 — SQLite

La versión de escritorio conserva el motor contable didáctico 2.1, los asientos, diarios, mayor, balances, calculadoras fiscales, los documentos y las exportaciones JSON/ZIP/PDF. Se sustituye el almacenamiento principal por SQLite incluido en la aplicación (rusqlite con SQLite bundled).

## Persistencia e aislamiento

Cada edición conserva su propio identificador y archivo **conta-fp360.sqlite3** dentro del directorio de datos de Tauri:

- Studio: es.atreyuserviciosdigitales.contafp360.studio
- Aula: es.atreyuserviciosdigitales.contafp360.aula

Rutas habituales: Windows, %APPDATA%/identificador; Linux, ~/.local/share/identificador; macOS, ~/Library/Application Support/identificador. Pueden variar con los ajustes del sistema o de Tauri.

Los datos se guardan en las tablas app_meta y stored_items. Se usan dos espacios independientes, local y objects, con claves compuestas, modo WAL y escritura síncrona FULL.

## Migración automática

En el primer inicio, antes de arrancar el motor JavaScript, se importan de localStorage los proyectos, diarios, actividades, resultados, estado de evaluación y preferencias de la edición correspondiente. Una marca interna impide reiniciar la migración posteriormente. En los inicios sucesivos, SQLite rehidrata la caché de localStorage para mantener la interfaz síncrona existente.

Aula utiliza SQLite para guardar el paquete docente (manifiesto y PDF). Los documentos binarios se codifican en Base64 al guardar y se reconstruyen como Uint8Array al recuperar el paquete. Cuando no hay paquete SQLite pero existe uno previo en IndexedDB, se migra automáticamente.

Las escrituras a localStorage se reflejan en SQLite mediante una cola secuencial. La aplicación sigue funcionando totalmente sin Internet, aunque una conexión externa para inteligencia artificial continuará necesitando red.

## Copias y restauración

Dos botones se encuentran al pie del menú lateral:

1. **Guardar copia SQLite**: guarda un archivo .sqlite3 con la API de copias online de SQLite, sin sobrescribir archivos de copia existentes.
2. **Restaurar copia SQLite**: pide confirmación, comprueba la integridad de la copia y verifica si pertenece a Studio o Aula. Antes de restaurarla guarda la situación anterior con un nombre del tipo antes-restauracion-<fecha>.sqlite3 en el directorio de datos, y recarga la aplicación al terminar.

La copia contiene todo lo almacenado en la base, incluidos documentos PDF y, en Studio, información docente. NO está cifrada. Custodiarla en un almacenamiento institucional seguro y no distribuir nunca copias de Studio ni claves docentes al alumnado.

La copia SQLite y las exportaciones educativas JSON/ZIP/PDF son complementarias: una copia SQLite de Studio no es un paquete didáctico intercambiable con Aula.

## Comprobaciones

El repositorio incluye tests de estructura, comprobación de sintaxis de JavaScript, y una prueba de navegador que simula los comandos nativos y comprueba la migración, edición y recuperación de PDF binarios y las exportaciones.

GitHub Actions compila los instaladores en Windows y Linux con SQLite incorporado. Deben completarse los ensayos de instalación real, persistencia tras cierre, copia y restauración en Windows/Linux y pruebas de exportación PDF/ZIP antes de declarar terminada la aceptación de esta versión. La compilación macOS sigue siendo una línea de trabajo independiente.

Autor y titular: Francisco Javier González Rolo. Reservados todos los derechos.
