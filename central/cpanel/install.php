<?php
declare(strict_types=1);
require __DIR__.'/bootstrap.php';
header('Content-Type: text/html; charset=utf-8');
header('X-Frame-Options: DENY');
$msg='';
try {
 $c=cfg();
 if (!is_string($c['install_secret']??null) || strlen($c['install_secret'])<24 || str_starts_with($c['install_secret'],'REEMPLAZAR')) throw new RuntimeException('Cambie install_secret de config.php por una clave aleatoria larga.');
 $db=db();
 $already=fetch_one("SELECT name FROM sqlite_master WHERE type='table' AND name='users'");
 if($already && (int)$db->query('SELECT COUNT(*) FROM users')->fetchColumn()>0){http_response_code(403);die('<h1>Instalación cerrada</h1><p>El servidor ya está inicializado. Elimine install.php del alojamiento.</p>');}
 if($_SERVER['REQUEST_METHOD']==='POST'){
  $secret=(string)($_POST['secret']??'');$name=trim((string)($_POST['school']??''));$person=trim((string)($_POST['name']??''));$email=strtolower(trim((string)($_POST['email']??'')));$password=(string)($_POST['password']??'');
  if(!hash_equals($c['install_secret'],$secret)||strlen($name)<3||strlen($person)<3||!filter_var($email,FILTER_VALIDATE_EMAIL)||strlen($password)<12)throw new RuntimeException('Clave, correo o datos incorrectos. Contraseña de al menos 12 caracteres.');
  $sql=file_get_contents(__DIR__.'/schema.sql');if($sql===false)throw new RuntimeException('Falta schema.sql');
  $db->exec($sql);
  if((int)$db->query('SELECT COUNT(*) FROM users')->fetchColumn()>0)throw new RuntimeException('La instalación ya existe.');
  $db->beginTransaction();
  try{$db->prepare('INSERT INTO schools(name) VALUES(?)')->execute([$name]);$school=(int)$db->lastInsertId();$db->prepare('INSERT INTO users(school_id,email,display_name,role,passhash) VALUES(?,?,?,?,?)')->execute([$school,$email,$person,'admin',password_hash($password,PASSWORD_DEFAULT)]);$db->commit();}
  catch(Throwable $e){if($db->inTransaction())$db->rollBack();throw $e;}
  $msg='Servidor instalado. Elimine install.php y entre en index.php.';
 }
} catch(Throwable $e){$msg=$e->getMessage();}
function e(string $s): string{return htmlspecialchars($s,ENT_QUOTES,'UTF-8');}
?><!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Instalación · CONTA FP360 Central</title><style>body{font:16px system-ui;max-width:620px;margin:5vh auto;padding:18px;color:#21344f}input{display:block;width:100%;padding:12px;margin:6px 0 16px;box-sizing:border-box}button{background:#194da0;color:#fff;border:0;border-radius:8px;padding:13px 22px}form{border:1px solid #d8dfeb;border-radius:12px;padding:25px}</style><h1>CONTA FP360 Central</h1><p>Instalación segura de la biblioteca educativa PHP/SQLite.</p><?php if($msg): ?><p role="alert"><?=e($msg)?></p><?php endif; ?><form method="post"><label>Clave de instalación<input type="password" name="secret" required></label><label>Centro educativo<input name="school" required></label><label>Nombre del administrador<input name="name" required></label><label>Correo electrónico<input type="email" name="email" required></label><label>Contraseña (mínimo 12 caracteres)<input type="password" name="password" minlength="12" required></label><button>Instalar servidor</button></form></html>
