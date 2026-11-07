<?php
/** Renombrar a config.php y editar ANTES de abrir install.php. No almacenar claves en GitHub. */
return [
    'install_secret' => 'REEMPLAZAR-CON-UNA-CLAVE-ALEATORIA-DE-32-CARACTERES',
    'base_url' => 'https://SU-DOMINIO.EJEMPLO/conta-fp360',
    'db_path' => dirname(__DIR__, 2) . '/.conta-fp360/conta-central.sqlite3',
    'upload_dir' => dirname(__DIR__, 2) . '/.conta-fp360/packages',
    'token_hours' => 8,
    'platform_owner_email' => 'REEMPLAZAR-CON-CORREO-DEL-ADMIN-PRINCIPAL',
    'require_curriculum_catalog' => true,
    'max_package_bytes' => 25 * 1024 * 1024,
    'max_submission_bytes' => 3 * 1024 * 1024,
];
