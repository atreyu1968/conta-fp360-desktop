<?php
/**
 * Router EXCLUSIVO de pruebas locales para php -S.
 * El servidor integrado ignora .htaccess: no usarlo en producción.
 */
declare(strict_types=1);
$root = realpath($_SERVER['DOCUMENT_ROOT']);
$path = rawurldecode(parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH) ?: '/');
if ($path === '/') $path = '/index.php';
$file = $root ? realpath($root.$path) : false;
$entry = in_array($path, ['/index.php', '/api.php'], true);
$asset = str_starts_with($path, '/assets/') && preg_match('/\.(?:css|js|png|svg|ico)$/D', $path);
if (!$root || !$file || !str_starts_with($file, $root.'/') || !is_file($file) || (!$entry && !$asset)) {
    http_response_code(404);
    header('Content-Type: text/plain; charset=utf-8');
    echo 'Recurso no disponible.';
    return true;
}
if ($entry) {
    require $file;
    return true;
}
return false;
