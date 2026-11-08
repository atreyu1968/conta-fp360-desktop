# Procedencia del código importado

Se ha importado el código existente de
https://github.com/atreyu1968/conta-fp360-desktop,
rama `feature/auditoria-integral-2026-11`, commit
`3296a947ccd0fb6a4475a7ac03004b5ecb7f801d`.
La estructura original (`web`, `src-tauri`, `central`, `tests`, scripts y CI)
se conserva: no se ha recreado la aplicación con un scaffold.

La URL solicitada inicialmente, `atreyu1968/Contafp360`, devolvía un repositorio
sin contenido durante la inspección del 8 de noviembre de 2026. El usuario facilitó
después el enlace anterior. No son el mismo repositorio.

En `main` solo estaban las aplicaciones de escritorio; la rama importada contiene
también Central PHP/SQLite. La adaptación de Ubuntu Server se documenta en
`UBUNTU_SERVER.md`. Studio y Aula no se convierten en aplicaciones web nuevas,
y Central no se convierte en una aplicación Tauri.

Los resultados históricos de GitHub Actions pertenecen al commit y rama de cada
ejecución, no validan automáticamente este código modificado. Las pruebas locales
de PHP/SQLite y las compilaciones de CI no sustituyen pruebas en equipos físicos,
firma/notarización de macOS ni un despliegue de servidor de producción.
