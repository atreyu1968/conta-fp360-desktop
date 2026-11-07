# CONTA FP360 Central — interfaz visual del panel cPanel

La edición visual mantiene la API PHP 8 + SQLite y **no cambia la base de datos ni el esquema académico**. La navegación funciona con JavaScript nativo y hojas CSS locales, sin CDN, evitando dependencias externas y respetando la política CSP de `index.php`.

## Principales espacios

- **Panel general:** indicadores de grupos, ejercicios, entregas, media de criterios evaluados; gráfico de RA con notas confirmadas y resumen de entregas.
- **Biblioteca:** filtro de búsqueda por título/código del módulo/identificador y RA.CE; selector de módulo; publicación mediante ZIP de alumnado con validación de API.
- **Grupos:** creación y matriculación desde los formularios existentes; listado de los grupos del profesor.
- **Asignaciones:** distribución de un ejercicio a un grupo y vista de las últimas asignaciones.
- **Evaluación RA/CE:** entregas, corrección manual, exportación JSON y matriz de criterios por alumno. Los resultados proceden de la API central, no de calificaciones inventadas en el navegador.
- **Administración:** alta de personas usuarias con permisos de administrador.
- **Alumnado:** lista de actividades asignadas; la resolución contable sigue correspondiendo a CONTA FP360 Aula offline.

Los indicadores de calificación muestran **«—»** cuando no existe nota completa; no confunden los trabajos recibidos con los corregidos. El módulo no pretende sustituir el procesamiento y control de seguridad del servidor.

## Instalación

Copie el directorio `central/cpanel` al alojamiento cPanel con la documentación de `central/README.md`. El archivo `index.php` carga, en este orden:

```html
<link rel="stylesheet" href="assets/dashboard.css">
<link rel="stylesheet" href="assets/visual.css">
<script src="assets/dashboard.js" defer></script>
<script src="assets/visual.js" defer></script>
```

Se mantienen los identificadores de los formularios y sus llamadas a `api.php`. El módulo `visual.js` escucha eventos propios del panel original para actualizar las vistas.

## Comprobaciones

- Sintaxis PHP y JavaScript, incluida `visual.js`.
- Integridad del esquema de datos y prueba HTTP integral con `central/tests/check_schema.py` y `central/tests/test_cpanel_http.py` (requiere PHP con `pdo_sqlite` y `zip`).
- Pruebas manuales/automatizadas de navegador: acceso con datos ficticios, biblioteca y filtros, cambio de vistas, perfil alumnado y diseño responsive.
- Probar antes de producción en cPanel real, con controles de seguridad y acceso para datos personales.

## Criterios de diseño

Interfaz accesible y adaptable a escritorio, portátil, tableta y móvil; no se incorporan dependencias de terceros. Los ejemplos de pantalla y pruebas utilizan nombres ficticios y no deben interpretarse como actividad real de los centros educativos.

**Nota:** Estas pantallas son un cliente web de administración; los cálculos contables y el trabajo educativo offline continúan dentro de Studio y Aula.