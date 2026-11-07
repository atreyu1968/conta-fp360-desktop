# CONTA FP360 Central + sincronización de escritorio (entrega de integración)

**Propósito:** alumnos y profesores trabajan sin Internet en Studio/Aula (SQLite local). El servidor cPanel solo gestiona usuarios, grupos, biblioteca, asignaciones, entregas y calificaciones RA/CE. GitHub Releases es el origen separado de las actualizaciones firmadas de escritorio.

Autor y titular: Francisco Javier González Rolo. Reservados todos los derechos. Proyecto educativo; no constituye software de facturación ni documentación fiscal oficial.

## 1. Instalación asistida sin clave (PHP 8.2+)

**Instalador 2.5:** crea por sí mismo `config.php`, SQLite, carpetas privadas y la cuenta administradora. No pide clave de autorización ni exige introducir rutas del alojamiento.

**IMPORTANTE — protección inicial:** sin una clave de instalación, cualquier visitante que llegue a `install.php` antes que tú puede registrar la primera cuenta administradora. Antes de extraer el ZIP, activa **cPanel → Privacidad de directorios** para proteger temporalmente la raíz del subdominio mediante las credenciales HTTP que tú establezcas. Esta protección es independiente de CONTA FP360 y se puede retirar tras instalar. Si el proveedor no ofrece esta función, restringe el acceso al instalador por IP o evita dejar el subdominio públicamente accesible mientras lo configuras.

1. Verifica que `conta.redfp360.net` tenga HTTPS activo, PHP 8.2+ y extensiones PDO_SQLITE, SQLite3 y ZipArchive.
2. Haz una copia de seguridad del `config.php` anterior y de cualquier base SQLite existente. Extrae los archivos del paquete nuevo en la carpeta web del subdominio, incluida `.htaccess`. El instalador no borra ni reescribe SQLite si contiene usuarios, ni migra automáticamente bases existentes.
3. Abre `https://conta.redfp360.net/install.php`; el formulario comprueba los requisitos de la máquina. Introduce **solamente** nombre del centro, administrador, correo y contraseña de 12+ caracteres. El botón `Instalar Central` crea `config.php` y SQLite fuera de la carpeta web y registra al administrador.
4. Comprueba `https://conta.redfp360.net/api.php?r=health` y accede al panel con la nueva cuenta. Si el instalador no logró borrarse, **elimina `install.php` manualmente** desde cPanel y verifica que no sigue siendo accesible. Después retira la protección temporal de directorios para que las aplicaciones puedan sincronizar sin autenticación HTTP adicional.
5. En Studio y Aula, introduce únicamente `https://conta.redfp360.net` como dirección de Central e inicia sesión con las cuentas personales creadas en el panel.

El instalador detecta HOME (en cPanel), crea `HOME/.conta-fp360/`, valida que sea privada y escribible, comprueba la disponibilidad real de PDO_SQLITE, y almacena allí el archivo `conta-central.sqlite3` y los paquetes ZIP. Al reparar una instalación previa que aún no contiene usuarios, conserva una copia privada de `config.php`. Si hay una base antigua que podría contener datos, se detiene para evitar daños.

**No confundir:** la contraseña del administrador de Central **sí es obligatoria** y distinta de la protección temporal del directorio de cPanel. El valor legado `install_secret` de instalaciones anteriores ya no se usa en el asistente. No exponer configuraciones, tokens o credenciales en GitHub ni dejar instaladores públicos. Antes de introducir datos reales de alumnado deben comprobarse permisos, protección de datos y copias consistentes de SQLite (WAL).

## 2. Uso del servidor

El administrador crea usuarios docentes y alumnos, identificados por centro. El profesor crea grupos, matricula alumnos existentes y genera un paquete `.zip` de alumnado usando la función «Publicar paquete» de Studio. Desde el panel `index.php` puede publicar el ZIP (con código de módulo, RA/CE y referencia curricular) y asignarlo a un grupo.

Aula recibe los paquetes asignados al conectarse. Trabaja offline en el diario, mayor, balances, documentación y actividades. Cuando el alumno prepara una entrega, el cliente la incorpora a una cola local con `event_id` único. El servidor solo confirma la entrega y no usa las notas procedentes del cliente como calificación oficial.

El profesor puede revisar entregas y registrar las notas validadas por CE e instrumento. El informe de grupo muestra por defecto **60 % portafolio + 40 % prueba objetiva solamente si los instrumentos con peso positivo están calificados** para el CE. La ponderación de cada módulo puede modificarse de forma explícita en el panel. Si falta alguno, el criterio permanece «pendiente»; el RA se calcula como media de sus CE una vez completos. Esta regla es un punto de partida específico configurable en una fase posterior para otras programaciones y módulos; no se atribuye a ningún currículo oficial sin su comprobación.

## 3. API REST v1

Todas las rutas se publican como `https://dominio/conta-fp360/api.php?r=NOMBRE` (no necesita reescritura URL). Métodos GET/POST; JSON y token Bearer, salvo `health` y `login`.

| Ruta | Método | Autorización | Función |
|---|---|---|---|
| health | GET | Público | Comprobar servicio |
| login / logout / me | POST / POST / GET | Según ruta | Sesión temporal |
| users | GET / POST | Docente y admin / admin | Consultar y crear usuarios |
| groups | GET / POST | Sesión / docente | Listado, creación |
| enroll | POST | Docente | Matricular a estudiante de su centro |
| library | GET / POST | Docente | Biblioteca y subida de ZIP de alumnado |
| assign | POST | Docente | Asignación a grupo |
| pull | GET | Sesión | Asignaciones visibles para ese usuario |
| package?id=N | GET | Sesión | Descargar ZIP autorizado |
| submit | POST | Alumno | Entrega idempotente con evento y número de intento |
| submissions?group_id=N | GET | Docente autorizado | Listar entregas |
| submission?id=N | GET | Docente autorizado | Consultar trabajo |
| grade | POST | Docente autorizado | Validar calificaciones por CE |
| report?group_id=N | GET | Docente autorizado | Matriz RA/CE por grupo |

**Límites de esta versión:** la biblioteca sigue siendo por centro, las notas del alumno requieren validación docente, no existe firma electrónica de entregas y cada catálogo curricular debe cargarse y comprobarse contra su fuente oficial. El alta de nuevos centros y el restablecimiento de contraseñas son ahora operaciones administrativas auditables, aunque no sustituyen una identidad institucional federada. Debe pilotarse con datos ficticios antes de manejar expedientes de alumnos reales.

## 4. Actualizador de escritorio

La integración actualizada del escritorio se mantiene en GitHub, en el mismo repositorio, bajo `web/studio/`, `web/aula/` y `src-tauri/`. El paquete distribuible de cPanel contiene **únicamente el servidor central y sus pruebas**, no los instaladores de escritorio. Actualizar desde GitHub implica **claves criptográficas de firma** (obligatorias por Tauri). La comprobación e instalación desde GitHub Releases permanece desactivada hasta generar una pareja de claves, guardar la privada en GitHub Actions Secrets y configurar la pública al compilar las aplicaciones. El certificado comercial de firma Windows y la firma/notarización macOS son requisitos de distribución adicionales, no sustitutos de la firma de actualizaciones.

La comprobación de versiones nunca depende del servidor cPanel. No instalar una actualización si existe alguna operación local de escritura pendiente; antes de cualquier migración de esquema debe existir una copia íntegra.

## 5. Verificaciones incluidas

- `php -l` para sintaxis de los PHP.
- `node --check` para JavaScript.
- `python tests/check_schema.py` para creación de tablas y restricciones de claves/roles/duplicados en SQLite real.
- `python tests/test_cpanel_http.py`: prueba HTTP completa (instalación, usuarios, roles, grupos, paquetes ZIP, asignaciones, entregas repetidas y tardías, calificaciones por CE, resultados RA y bloqueo de intentos). **Requiere PHP con `pdo_sqlite` y `ZipArchive`**. La prueba HTTP completa se ha ejecutado satisfactoriamente en GitHub Actions con PHP 8.3, PDO_SQLITE y ZIP. El entorno local utilizado para crear el ZIP no dispone de esas extensiones. Todavía se requiere una prueba adicional en un cPanel real.

## 6. Seguridad y protección de datos

Este proyecto es una **base de integración**, no un servicio homologado para producción educativa. Antes de desplegarlo, verificar con el delegado de protección de datos y el responsable del tratamiento: base jurídica, perfiles de usuario, consentimiento cuando sea exigible, retención, sede y contratos con el proveedor cPanel, transferencia de datos, evaluación de riesgos, cifrado de copias, secreto profesional y protocolo de incidentes.

No subir ZIP de Studio que incluyan las soluciones maestras a la biblioteca de alumnado. El servidor solo admite `manifest.json` de alumnado; la verificación automática de ausencia de soluciones no sustituye una revisión docente del paquete. Las autenticaciones son efímeras y los clientes no almacenan contraseñas ni tokens persistentes. No se confía en puntuaciones enviadas por el estudiante.

## 7. Cambios de seguridad y entregas offline (revisión 2.3)

- Se limita el inicio de sesión a ocho fallos por IP/correo y ventana de 15 minutos. Se registran identificadores hash, no direcciones IP ni contraseñas en claro.
- Un evento de entrega (`event_id`) repetido se confirma solo si el contenido, intento, asignación y alumno coinciden exactamente. Si difieren, el servidor devuelve 409.
- Una entrega procedente de un ordenador offline se recibe aunque el plazo haya vencido: se registra `late=1` según la hora del servidor para que el profesor decida su tratamiento. La fecha declarada por el alumno no sustituye a la hora del servidor.
- El servidor no transforma las calificaciones provisionales enviadas por Aula en calificaciones definitivas. El profesorado debe revisar y calificar las evidencias en el panel.
- El perfil local de una aplicación está vinculado al primer usuario y servidor autenticados. En equipos compartidos, cada alumno necesita un usuario separado del sistema operativo; la base SQLite de la misma cuenta del sistema **no está diseñada aún para varios estudiantes**.
- Las extensiones de PHP y las directivas de protección del directorio privado deben verificarse en el hosting antes de cualquier uso con datos reales.

### Verificación técnica de instalación

Ejecute en un entorno de pruebas con módulos PHP habilitados:

```bash
php -m | grep -Ei 'pdo_sqlite|zip'
python3 tests/check_schema.py
python3 tests/test_cpanel_http.py
```

La última prueba crea un servidor PHP local sobre `127.0.0.1` con datos ficticios, construye paquetes ZIP de prueba y elimina sus datos al finalizar. No utiliza usuarios reales ni publica contenidos en Internet.
## 8. Refuerzo de seguridad y nueva versión funcional (auditoría noviembre 2026)

**Cambios disponibles en la rama de consolidación `feature/auditoria-integral-2026-11`:**

- Biblioteca local de **varios ZIP de alumnado** en SQLite, indexada por alumno y asignación; un ejercicio descargado puede volver a abrirse offline, conservando el diario y las actividades asociadas a su identificador.
- Las publicaciones de biblioteca y asignaciones reintentadas responden `already_received=true` cuando el contenido y los parámetros son idénticos. Un mismo identificador/revisión con contenido distinto devuelve 409 y no se sobrescribe.
- Las entregas del alumnado se confirman por `event_id` único. Las evidencias RA/CE remitidas por Aula son **informativas y no califican automáticamente** sin intervención del profesor.
- Para altas nuevas, las contraseñas son temporales y deben sustituirse antes de operar. `change_password` permite al titular cambiarla con su clave actual; `reset_password` permite a un administrador del mismo centro restablecer las de docentes y alumnos, revocando sus sesiones.
- Cada cambio de nota crea un asiento en `grade_history` con profesor, fecha, criterio, instrumento, anterior y nuevo valor. No se confían notas automáticas del alumno como definitivas.
- `grading_policy` configura los pesos de portafolio y prueba por módulo; el valor inicial 60/40 responde a la programación solicitada, no a una norma general. Cada CE recibe igual peso, y cada RA se promedia por sus criterios completos.
- `curricula` registra el **catálogo oficial de códigos** RA/CE aportado y contrastado por el administrador, con territorio, versión y URL. No se generan RA o CE de manera automática. Si `require_curriculum_catalog=true`, no se publica un ejercicio sin catálogo del módulo; cualquier código ajeno se rechaza.
- `schools` permite al administrador general indicado mediante `platform_owner_email` crear centros y sus administradores independientes; **no** comparte calificaciones de un centro con otro.
- Se ha corregido el panel gráfico RA/CE para evitar atributos de estilo inline incompatibles con la Content Security Policy. Las ediciones Tauri utilizan CSP restringida con recursos de aplicación locales y conexiones HTTPS.
- Las migraciones de las nuevas tablas son aditivas (`features.php`); no sustituyen ni borran las tablas de notas antiguas.

### Preparar `config.php` sin exponer datos

Edite una **copia privada** de `config.example.php` y sitúela como `config.php` solo en su alojamiento. **No la añada al repositorio público**.

La instalación asistida detecta una carpeta privada en HOME; no necesita editar manualmente rutas de SQLite. Verifique la privacidad de ese destino y no publique contraseñas, tokens o claves de IA en incidencias.

Defina `platform_owner_email` con la cuenta inicial administrativa si pretende habilitar el alta multicentro; de lo contrario, deje un valor que no coincida con usuarios para desactivar esa posibilidad.

El valor `require_curriculum_catalog` debería ser `true` en producción para impedir asignaciones con referencias curriculares sin verificar. El administrador debe cargar primero el currículo vigente desde el menú de administración.

### Usuarios y claves temporales

El administrador crea cuentas con contraseña temporal, comunicada mediante canal seguro. En el primer acceso el usuario recibe la obligación de cambiarla. Esta operación revoca todas sus sesiones, incluida la actual. La recuperación administrativa también revoca tokens y obliga a sustituir la clave antes de acceder a datos del centro.

**En equipos compartidos**, utilice cuentas independientes del sistema operativo: la base SQLite personal no cifra y aísla por sí sola las actividades de alumnos que utilicen la misma cuenta local. No se admite como equivalente una mera selección de usuarios dentro de la misma cuenta del sistema.

### Matriz de aceptación obligatoria antes de producción

1. Instalar servidor con PHP 8.2+ y comprobar `pdo_sqlite`, `sqlite3`, `ZipArchive`, HTTPS, ubicación privada de SQLite y reglas del hosting.
2. Registrar oficialmente módulos, versiones curriculares y códigos RA/CE. Verificar manualmente con BOE y normativa autonómica vigente.
3. Alta de administrador, docente y alumno, primer cambio de contraseña, revocación y restablecimiento; comprobar permisos entre centros.
4. Publicar ejercicio ZIP desde Studio, reintentarlo tras cortar la confirmación, asignarlo a un grupo y verificar que no aparecen duplicados.
5. Descargar **tres ejercicios** en Aula, desconectar, alternar entre ellos y reiniciar; comprobar que cada uno conserva documentos, asientos y actividades.
6. Reconectar, enviar una entrega dos veces con el mismo evento, registrar calificaciones, modificar una nota y consultar la auditoría y la matriz por CE/RA.
7. Generar dos `GitHub Releases` firmadas consecutivas y probar actualizaciones Tauri en instalaciones reales, incluidos respaldos SQLite y reversión por fallo.
8. Auditar la privacidad, contratos de tratamiento, retención, copias consistentes WAL, recuperación de desastres y la carga concurrente del hosting.

**Estado de distribución:** código y CI **no equivalen** a pruebas físicas del instalador, despliegue real en cPanel, firma comercial de Windows, Apple Developer ID/notarización ni aceptación institucional para datos personales. No publicar como versión estable hasta cerrar estos puntos.
