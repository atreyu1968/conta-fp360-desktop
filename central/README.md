# CONTA FP360 Central + sincronización de escritorio (entrega de integración)

**Propósito:** alumnos y profesores trabajan sin Internet en Studio/Aula (SQLite local). El servidor cPanel solo gestiona usuarios, grupos, biblioteca, asignaciones, entregas y calificaciones RA/CE. GitHub Releases es el origen separado de las actualizaciones firmadas de escritorio.

Autor y titular: Francisco Javier González Rolo. Reservados todos los derechos. Proyecto educativo; no constituye software de facturación ni documentación fiscal oficial.

## 1. Instalación en cPanel (PHP 8.2+)

Requisitos del alojamiento: PHP 8.2 o superior, `PDO`, `pdo_sqlite`, `SQLite3`, `ZipArchive` (`zip`), HTTPS, permisos de escritura para la carpeta privada. Si una extensión no aparece en «Select PHP Version» o «PHP Extensions», deberá habilitarla el proveedor. Para subir paquetes de hasta 25 MB, comprobar `post_max_size` y `memory_limit` (se recomienda `post_max_size` ≥ 40 MB, `memory_limit` ≥ 128 MB). SQLite en hospedaje compartido es apropiado para concurrencia moderada, no para cargas masivas; la estrategia WAL y `busy_timeout` minimiza los bloqueos pero no sustituye pruebas con usuarios reales.

1. Subir el contenido de `cpanel/` a `public_html/conta-fp360/` usando cPanel File Manager (no descomprimir el archivo principal dejando doble directorio).
2. Renombrar `config.example.php` a `config.php` y editar `base_url` (HTTPS) e `install_secret` con 32 o más caracteres aleatorios. **Jamás subir `config.php` ni contraseñas a GitHub.**
3. Preferentemente cambiar `db_path` y `upload_dir` para que apunten a carpetas privadas **fuera de `public_html`**. Si quedan bajo `cpanel/private`, asegurarse de que Apache/LiteSpeed respeta `Require all denied` y comprobar mediante URL que la carpeta es inaccesible. Nginx sin `.htaccess` requiere reglas equivalentes del proveedor.
4. Abrir `https://DOMINIO/conta-fp360/install.php`. Introducir la clave inicial, centro educativo, administrador, correo y contraseña de al menos 12 caracteres.
5. Cuando confirme la instalación, **eliminar `install.php` del alojamiento**. Acceder al panel `index.php` para crear usuarios, grupos, matrículas y asignaciones.
6. Configurar copia periódica del archivo SQLite con método seguro y directorio de paquetes, preferentemente con una tarea cron y backups del proveedor; la simple copia de un archivo WAL activo no constituye una copia consistente. Configurar protección de datos, retención, encargos de tratamiento y control de permisos antes de registrar alumnado real.

El acceso **no permite registro público**, ni publica contraseñas de ejemplo. La primera configuración está protegida por `install_secret` que el propietario define localmente.

## 2. Uso del servidor

El administrador crea usuarios docentes y alumnos, identificados por centro. El profesor crea grupos, matricula alumnos existentes y genera un paquete `.zip` de alumnado usando la función «Publicar paquete» de Studio. Desde el panel `index.php` puede publicar el ZIP (con código de módulo, RA/CE y referencia curricular) y asignarlo a un grupo.

Aula recibe los paquetes asignados al conectarse. Trabaja offline en el diario, mayor, balances, documentación y actividades. Cuando el alumno prepara una entrega, el cliente la incorpora a una cola local con `event_id` único. El servidor solo confirma la entrega y no usa las notas procedentes del cliente como calificación oficial.

El profesor puede revisar entregas y registrar las notas validadas por CE e instrumento. El informe de grupo muestra **60 % portafolio + 40 % prueba objetiva solamente si ambos instrumentos están calificados** para el CE. Si falta alguno, el criterio permanece «pendiente»; el RA se calcula como media de sus CE una vez completos. Esta regla es un punto de partida específico configurable en una fase posterior para otras programaciones y módulos; no se atribuye a ningún currículo oficial sin su comprobación.

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

**Límites de esta versión:** sin sincronización multi-empresa entre centros, sin sustitución automática de credenciales olvidadas, sin sincronización bidireccional de correcciones ya recibidas por Aula, sin firma electrónica de entregas y sin aprobación de todos los currículos autonómicos. Debe pilotarse con datos ficticios antes de manejar expedientes de alumnos reales.

## 4. Actualizador de escritorio

La integración actualizada del escritorio se mantiene en GitHub, en el mismo repositorio, bajo `web/studio/`, `web/aula/` y `src-tauri/`. Este ZIP contiene **únicamente el servidor cPanel y sus pruebas**, no los instaladores de escritorio. Actualizar desde GitHub implica **claves criptográficas de firma** (obligatorias por Tauri). La comprobación e instalación desde GitHub Releases permanece desactivada hasta generar una pareja de claves, guardar la privada en GitHub Actions Secrets y configurar la pública al compilar las aplicaciones. El certificado comercial de firma Windows y la firma/notarización macOS son requisitos de distribución adicionales, no sustitutos de la firma de actualizaciones.

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