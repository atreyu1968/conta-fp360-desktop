<?php
/**
 * PLANTILLA PARA SOPORTE / MIGRACIONES.
 *
 * NO ES NECESARIO CREAR NI EDITAR ESTE ARCHIVO PARA UNA INSTALACIÓN NUEVA:
 * https://conta.redfp360.net/install.php detecta el HOME de cPanel, crea la
 * carpeta privada, valida SQLite y genera config.php automáticamente.
 *
 * Si se edita manualmente, reemplazar usuario y claves, y situar TODAS
 * las rutas de datos fuera de public_html y de cualquier document root.
 */
return [
    'install_secret' => 'REEMPLAZAR-CON-UNA-CLAVE-ALEATORIA-DE-32-CARACTERES',
    'base_url' => 'https://conta.redfp360.net',
    'db_path' => '/home/TU_USUARIO_CPANEL/.conta-fp360/conta-central.sqlite3',
    'upload_dir' => '/home/TU_USUARIO_CPANEL/.conta-fp360/packages',
    'token_hours' => 8,
    'platform_owner_email' => 'REEMPLAZAR-CON-CORREO-DEL-ADMIN-PRINCIPAL',
    'require_curriculum_catalog' => true,
    'max_package_bytes' => 25 * 1024 * 1024,
    'max_submission_bytes' => 3 * 1024 * 1024,
];
