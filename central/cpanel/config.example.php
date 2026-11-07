<?php
/** Renombrar a config.php y editar ANTES de abrir install.php. No almacenar claves en GitHub. */
return [
    'install_secret' => 'REEMPLAZAR-CON-UNA-CLAVE-ALEATORIA-DE-32-CARACTERES',
    'base_url' => 'https://SU-DOMINIO.EJEMPLO/conta-fp360',
    'db_path' => __DIR__ . '/private/conta-central.sqlite3',
    'upload_dir' => __DIR__ . '/private/packages',
    'token_hours' => 8,
    'max_package_bytes' => 25 * 1024 * 1024,
    'max_submission_bytes' => 3 * 1024 * 1024,
];
