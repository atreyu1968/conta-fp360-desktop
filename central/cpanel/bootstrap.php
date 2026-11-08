<?php
declare(strict_types=1);
function config_file_path(): string {
  $external = getenv('CONTA_CONFIG_FILE') ?: ($_SERVER['CONTA_CONFIG_FILE'] ?? '');
  if ($external !== '') {
    if (!is_string($external) || !str_starts_with($external, '/')) {
      throw new RuntimeException('CONTA_CONFIG_FILE debe ser una ruta absoluta.');
    }
    return $external;
  }
  return __DIR__.'/config.php';
}
function cfg(): array {
  static $c = null;
  if ($c !== null) return $c;
  $file = config_file_path();
  if (!is_file($file)) throw new RuntimeException('Falta la configuración de Central. Consulte la guía de instalación.');
  $c = require $file;
  if (!is_array($c) || !isset($c['db_path'],$c['upload_dir'])) throw new RuntimeException('Configuración incompleta');
  return $c;
}
function db(): PDO {
  static $db = null;
  if ($db) return $db;
  $c = cfg();
  $dir = dirname($c['db_path']);
  if (!is_dir($dir) && !mkdir($dir,0700,true) && !is_dir($dir)) throw new RuntimeException('Directorio de datos inaccesible');
  $db = new PDO('sqlite:'.$c['db_path'],null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC]);
  $db->exec('PRAGMA foreign_keys=ON; PRAGMA busy_timeout=5000; PRAGMA journal_mode=WAL;');
  return $db;
}
function json_in(): array {
  $limit=(int)(cfg()['max_submission_bytes']??3145728) + (int)(cfg()['max_package_bytes']??0)*2;
  if ((int)($_SERVER['CONTENT_LENGTH']??0) > $limit) fail(413,'Petición demasiado grande');
  $raw=file_get_contents('php://input',false,null,0,$limit+1);
  if ($raw === false || strlen($raw)>$limit) fail(413,'Petición demasiado grande');
  try { $decoded=json_decode($raw,true,512,JSON_THROW_ON_ERROR); }
  catch(Throwable $e){ fail(400,'JSON no válido'); }
  if (!is_array($decoded)) fail(400,'El cuerpo debe ser un objeto JSON');
  return $decoded;
}
function respond(array $payload,int $status=200): never {
  http_response_code($status); header('Content-Type: application/json; charset=utf-8');
  header('Cache-Control: no-store'); echo json_encode($payload,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR); exit;
}
function fail(int $status,string $message): never { respond(['ok'=>false,'error'=>$message],$status); }
function required_string(array $a,string $key,int $max=255): string {
  $v=$a[$key]??null;
  if (!is_string($v) || trim($v)==='' || strlen($v)>$max) fail(422,'Campo incorrecto: '.$key);
  return trim($v);
}
function fetch_one(string $sql,array $params=[]): ?array {
  $stmt=db()->prepare($sql); $stmt->execute($params); $row=$stmt->fetch(); return $row?:null;
}
function fetch_all(string $sql,array $params=[]): array {
  $stmt=db()->prepare($sql); $stmt->execute($params); return $stmt->fetchAll();
}
function require_auth(array $roles=[]): array {
  $header=(string)($_SERVER['HTTP_AUTHORIZATION']??$_SERVER['REDIRECT_HTTP_AUTHORIZATION']??'');
  if (!preg_match('/^Bearer ([A-Za-z0-9_-]{32,160})$/',$header,$m)) fail(401,'Autenticación necesaria');
  $row=fetch_one('SELECT u.id,u.school_id,u.role,u.display_name,u.email FROM tokens t JOIN users u ON u.id=t.user_id WHERE t.hash=? AND t.expires_at>? AND u.active=1',[hash('sha256',$m[1]),time()]);
  if (!$row) fail(401,'Sesión caducada o no autorizada');
  if ($roles && !in_array($row['role'],$roles,true)) fail(403,'Permisos insuficientes');
  return $row;
}
function teacher_group(int $groupId,array $user): array {
  $g=fetch_one('SELECT * FROM groups WHERE id=?',[$groupId]);
  if (!$g || (int)$g['school_id']!==(int)$user['school_id'] || ($user['role']!=='admin' && (int)$g['teacher_id']!==(int)$user['id'])) fail(403,'Grupo no autorizado');
  return $g;
}
function student_assigned(int $assignmentId,array $user): array {
  $row=fetch_one('SELECT a.*,e.id AS exercise_id_real,e.external_id,e.title,e.module_code,e.criteria_json,e.zip_path,e.sha256 FROM assignments a JOIN enrollments en ON en.group_id=a.group_id AND en.student_id=? JOIN exercises e ON e.id=a.exercise_id JOIN groups g ON g.id=a.group_id WHERE a.id=? AND g.school_id=?',[$user['id'],$assignmentId,$user['school_id']]);
  if (!$row) fail(403,'Ejercicio no asignado a este alumno');
  return $row;
}
function criteria_for(array $exercise): array {
  $items=json_decode($exercise['criteria_json'],true)??[];
  $result=[];
  foreach($items as $item) if(is_array($item) && isset($item['code'],$item['ra'])) $result[(string)$item['code']]=(string)$item['ra'];
  return $result;
}
