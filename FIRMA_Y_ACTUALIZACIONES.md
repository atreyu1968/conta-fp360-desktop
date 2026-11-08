# CONTA FP360 · firma de actualizaciones y publicación (Tauri 2)

Guía para el titular del repositorio **atreyu1968/conta-fp360-desktop**.

> Las claves privadas de firma **no se generan en GitHub Actions**, no se incorporan a commits ni se pegan en un chat. Se generan en un ordenador de confianza, se guardan en un lugar seguro y su contenido se configura como GitHub Actions Secret. Las firmas Tauri del actualizador no sustituyen Authenticode de Windows ni Developer ID/notarización de Apple.

## 1. Generar un par de claves Tauri una sola vez

Requisito: Node.js LTS y npm. En Windows, abra **PowerShell** con su usuario normal:

```powershell
npm install --global @tauri-apps/cli@2
New-Item -ItemType Directory -Force "$env:USERPROFILE\.tauri" | Out-Null
tauri signer generate -w "$env:USERPROFILE\.tauri\conta-fp360.key"
```

Introduzca y recuerde **una contraseña robusta**. La herramienta genera, junto a la clave privada, un archivo público `conta-fp360.key.pub`. Guarde la clave privada y la contraseña por separado, en copias cifradas.

En macOS/Linux:

```bash
npm install --global @tauri-apps/cli@2
mkdir -p "$HOME/.tauri"
tauri signer generate -w "$HOME/.tauri/conta-fp360.key"
```

No publique los dos archivos en el repositorio; la clave pública puede compartirse, pero la privada no.

## 2. Configurar GitHub Actions

Abra https://github.com/atreyu1968/conta-fp360-desktop/settings/secrets/actions

En **Repository secrets** > **New repository secret**, cree:

| Nombre exacto | Valor |
| --- | --- |
| `TAURI_SIGNING_PRIVATE_KEY` | Contenido textual **completo** de `conta-fp360.key`, no la ruta |
| `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` | Contraseña indicada al generar la clave |

En **Variables** > **New repository variable**, cree:

| Nombre exacto | Valor |
| --- | --- |
| `CONTA_FP360_UPDATER_PUBKEY` | Contenido textual **completo** de `conta-fp360.key.pub`, no la ruta |

Para leer en PowerShell sin imprimir ni compartir en el chat:

```powershell
Get-Content -Raw "$env:USERPROFILE\.tauri\conta-fp360.key.pub"
```

Para la clave privada, ábrala en un editor local y péguela **exclusivamente** en el formulario cifrado de GitHub. No la suba como archivo público. Si se dispone de GitHub CLI autenticado localmente, también se puede usar `gh secret set TAURI_SIGNING_PRIVATE_KEY < ruta/al/archivo.key`, pero **nunca** pase la clave como argumento de línea de comandos visible en el historial.

La variable pública `CONTA_FP360_UPDATER_PUBKEY` se embebe en el binario a través de `option_env!` de Rust durante la compilación. Los usuarios no deben editarla ni facilitar una clave propia: las claves de publicación pertenecen al titular del proyecto.

## 3. Publicación segura

1. Compruebe que CI Windows, Linux, macOS y Central son satisfactorios.
2. Fusione PR #2 únicamente después de validar el circuito educativo. No etiquete una rama de pruebas como producción.
3. Compruebe la versión en `src-tauri/tauri.conf.json` y `src-tauri/Cargo.toml` (deben coincidir).
4. En GitHub cree una etiqueta `vX.Y.Z` sobre el commit verificado de `main`, coincidente con la versión del ejecutable. Ejemplo: `v2.3.0`.
5. El workflow `.github/workflows/release.yml` compila y firma los artefactos de **Studio y Aula** para Windows x64, Linux x64, macOS Intel y Apple Silicon.
6. La publicación adjunta `studio-latest.json` y `aula-latest.json`. El actualizador comprueba de forma independiente la firma para cada sistema.

**No repetir etiquetas existentes ni reutilizar números de versión:** para comprobar una actualización real instale, por ejemplo, la v2.3.0 en un equipo y publique posteriormente v2.3.1 con el mismo par de claves.

IMPORTANTE: la clave del actualizador debe estar configurada **antes de compilar la primera versión que se distribuya al alumnado**, para que esos binarios incluyan la clave pública correcta.

## 4. Firma del sistema operativo (proceso independiente)

### Windows
- La firma Tauri permite verificar actualizaciones, pero no elimina los avisos de SmartScreen de un instalador Windows sin **certificado de firma de código**.
- Los instaladores pueden utilizarse durante las pruebas sin certificado comercial con las restricciones de seguridad del equipo. En Windows 11 con Smart App Control pueden bloquearse.
- Cuando se obtenga certificado para persona física o un servicio de firma en la nube, se añadirá al workflow el proveedor elegido y el firmado Authenticode de los instaladores. No comparta archivos PFX ni credenciales por chat.

### macOS
- La firma criptográfica Tauri **tampoco** sustituye una identidad Developer ID y la **notarización de Apple**.
- Para pruebas ad-hoc en Macs, la firma `signingIdentity: "-"` es posible, pero macOS puede exigir autorización manual.
- Para distribuir sin advertencias habituales, se requiere inscripción en Apple Developer, certificado Developer ID Application y notarización. Los secretos/credenciales se configuran en GitHub Actions exclusivamente una vez que se obtengan.
- No considere completa la distribución de macOS antes de probar instalación, notarización y reemplazo en un Mac Intel y uno Apple Silicon.

## 5. Seguridad y mantenimiento

- Proteja las etiquetas y los permisos de escritura del repositorio. La rama de publicación debe estar protegida.
- No ejecute workflows de publicación desde cambios no revisados ni habilite que contribuciones externas accedan a los secretos.
- Mantenga al menos dos copias cifradas y fuera de GitHub de la clave privada de Tauri.
- No cambie la clave Tauri a la ligera: la rotación requiere un proceso de transición para las aplicaciones antiguas.
- La actualización no debe borrar el SQLite de usuario. Haga y pruebe copias de seguridad.
- Pruebe el manifiesto y verifique `*.sig` en una primera publicación controlada, antes de publicar para centros educativos.

## Enlaces oficiales

- https://v2.tauri.app/plugin/updater/
- https://v2.tauri.app/distribute/pipelines/github/
- https://v2.tauri.app/distribute/sign/windows/
- https://v2.tauri.app/distribute/sign/macos/
- https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets
