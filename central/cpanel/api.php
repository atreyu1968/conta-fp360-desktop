<?php
declare(strict_types=1);
require __DIR__.'/bootstrap.php';
require __DIR__.'/features.php';
header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: no-referrer');
$origin=(string)($_SERVER['HTTP_ORIGIN']??'');
if ($origin && in_array($origin,['tauri://localhost','http://tauri.localhost','https://tauri.localhost','http://localhost:1420','http://127.0.0.1:1420'],true)) {
 header('Access-Control-Allow-Origin: '.$origin);
 header('Vary: Origin');
 header('Access-Control-Allow-Headers: Authorization, Content-Type');
 header('Access-Control-Allow-Methods: GET, POST, OPTIONS');
 header('Access-Control-Max-Age: 600');
}
if ($_SERVER['REQUEST_METHOD']==='OPTIONS') { http_response_code(204); exit; }
try {
 $route=(string)($_GET['r']??'health'); $method=$_SERVER['REQUEST_METHOD'];
 if ($route==='health' && $method==='GET') {
   $c=cfg(); respond(['ok'=>true,'service'=>'conta-fp360-central','api'=>'v1','initialized'=>is_file($c['db_path'])]);
 }
 $db=db();
 if (!fetch_one("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")) fail(503,'El servidor todavía no está instalado');
 ensure_central_features($db);
 if ($route==='login' && $method==='POST') {
   $in=json_in(); $email=strtolower(required_string($in,'email',240));$pass=required_string($in,'password',500);
   // Limitación de fuerza bruta por pareja IP/correo, sin almacenar contraseñas ni IP en claro.
   $remote=(string)($_SERVER['REMOTE_ADDR']??'unknown');
   $attemptKey=hash('sha256',$remote.'|'.$email);
   $attempt=fetch_one('SELECT failures,reset_after FROM auth_attempts WHERE key_hash=?',[$attemptKey]);
   if($attempt && (int)$attempt['reset_after']>time() && (int)$attempt['failures']>=8)fail(429,'Demasiados intentos; pruebe de nuevo más tarde');
   $u=fetch_one('SELECT * FROM users WHERE email=? AND active=1',[$email]);
   if (!$u || !password_verify($pass,$u['passhash'])) {
     if(!$attempt || (int)$attempt['reset_after']<=time())$db->prepare('INSERT INTO auth_attempts(key_hash,failures,reset_after) VALUES(?,?,?) ON CONFLICT(key_hash) DO UPDATE SET failures=excluded.failures,reset_after=excluded.reset_after')->execute([$attemptKey,1,time()+900]);
     else $db->prepare('UPDATE auth_attempts SET failures=failures+1 WHERE key_hash=?')->execute([$attemptKey]);
     fail(401,'Credenciales incorrectas');
   }
   $db->prepare('DELETE FROM auth_attempts WHERE key_hash=?')->execute([$attemptKey]);
   $token=rtrim(strtr(base64_encode(random_bytes(48)),'+/','-_'),'=');
   $expire=time()+(int)(cfg()['token_hours']??8)*3600;
   $db->prepare('DELETE FROM tokens WHERE expires_at<=?')->execute([time()]);
   $db->prepare('INSERT INTO tokens(hash,user_id,expires_at,created_at) VALUES(?,?,?,?)')->execute([hash('sha256',$token),$u['id'],$expire,time()]);
   $flag=fetch_one('SELECT must_change FROM password_flags WHERE user_id=?',[$u['id']]);
   respond(['ok'=>true,'token'=>$token,'expires_at'=>$expire,'user'=>['id'=>(int)$u['id'],'name'=>$u['display_name'],'role'=>$u['role'],'school_id'=>(int)$u['school_id'],'must_change_password'=>$flag?(bool)$flag['must_change']:false]]);
 }
 if ($route==='logout' && $method==='POST') {
   $u=require_auth();$header=(string)($_SERVER['HTTP_AUTHORIZATION']??'');
   $db->prepare('DELETE FROM tokens WHERE hash=?')->execute([hash('sha256',substr($header,7))]);respond(['ok'=>true]);
 }
 $u=require_auth();
 if ($route==='change_password' && $method==='POST') {
   $in=json_in();$current=required_string($in,'current_password',500);$new=required_string($in,'new_password',500);
   secure_new_password($new);
   $account=fetch_one('SELECT passhash FROM users WHERE id=?',[$u['id']]);
   if(!$account||!password_verify($current,$account['passhash']))fail(401,'Contraseña actual incorrecta');
   if(password_verify($new,$account['passhash']))fail(422,'La nueva contraseña debe ser distinta');
   $db->beginTransaction();
   try {
     $db->prepare('UPDATE users SET passhash=? WHERE id=?')->execute([password_hash($new,PASSWORD_DEFAULT),$u['id']]);
     $db->prepare('INSERT INTO password_flags(user_id,must_change) VALUES(?,0) ON CONFLICT(user_id) DO UPDATE SET must_change=0,updated_at=CURRENT_TIMESTAMP')->execute([$u['id']]);
     $db->prepare('DELETE FROM tokens WHERE user_id=?')->execute([$u['id']]);
     $db->commit();
   }catch(Throwable $e){if($db->inTransaction())$db->rollBack();throw $e;}
   respond(['ok'=>true,'relogin_required'=>true]);
 }
 $flag=fetch_one('SELECT must_change FROM password_flags WHERE user_id=?',[$u['id']]);
 if($flag && (int)$flag['must_change']===1)fail(403,'Debe cambiar su contraseña temporal antes de continuar');
 if ($route==='me' && $method==='GET') respond(['ok'=>true,'user'=>$u]);
 if ($route==='reset_password' && $method==='POST') {
   require_auth(['admin']);$in=json_in();$uid=(int)($in['user_id']??0);$new=required_string($in,'new_password',500);
   secure_new_password($new);
   $target=fetch_one('SELECT id FROM users WHERE id=? AND school_id=? AND role IN (\'teacher\',\'student\')',[$uid,$u['school_id']]);
   if(!$target)fail(403,'Solo puede restablecer cuentas docentes o de alumnos de su centro');
   $db->beginTransaction();
   try {
      $db->prepare('UPDATE users SET passhash=? WHERE id=?')->execute([password_hash($new,PASSWORD_DEFAULT),$uid]);
      $db->prepare('INSERT INTO password_flags(user_id,must_change) VALUES(?,1) ON CONFLICT(user_id) DO UPDATE SET must_change=1,updated_at=CURRENT_TIMESTAMP')->execute([$uid]);
      $db->prepare('DELETE FROM tokens WHERE user_id=?')->execute([$uid]);
      $db->commit();
   }catch(Throwable $e){if($db->inTransaction())$db->rollBack();throw $e;}
   respond(['ok'=>true,'must_change_password'=>true]);
 }
 if ($route==='curricula' && $method==='GET') {
   require_auth(['admin','teacher']);$rows=fetch_all('SELECT module_code,territory,source_url,version,criteria_json,updated_at FROM curriculum_catalogs WHERE school_id=? ORDER BY module_code',[$u['school_id']]);
   foreach($rows as &$row){$row['criteria']=json_decode($row['criteria_json'],true);unset($row['criteria_json']);}
   respond(['ok'=>true,'items'=>$rows]);
 }
 if ($route==='curricula' && $method==='POST') {
   require_auth(['admin']);$in=json_in();$code=required_string($in,'module_code',40);
   $territory=required_string($in,'territory',100);$version=required_string($in,'version',100);$url=required_string($in,'source_url',1000);
   if(!preg_match('/^https:\/\//i',$url))fail(422,'La referencia curricular debe utilizar HTTPS');
   $items=$in['criteria']??null;
   if(!is_array($items)||!count($items)||count($items)>600)fail(422,'Debe aportar criterios oficiales verificables');
   $criteria=[];foreach($items as $entry){
     if(!is_string($entry)||!preg_match('/^RA[1-9][0-9]*\.[a-z]$/',$entry)||in_array($entry,$criteria,true))fail(422,'Código curricular incorrecto o duplicado');
     $criteria[]=$entry;
   }
   $db->prepare('INSERT INTO curriculum_catalogs(school_id,module_code,territory,source_url,version,criteria_json,updated_by) VALUES(?,?,?,?,?,?,?) ON CONFLICT(school_id,module_code) DO UPDATE SET territory=excluded.territory,source_url=excluded.source_url,version=excluded.version,criteria_json=excluded.criteria_json,updated_by=excluded.updated_by,updated_at=CURRENT_TIMESTAMP')
     ->execute([$u['school_id'],$code,$territory,$url,$version,json_encode($criteria,JSON_THROW_ON_ERROR),$u['id']]);
   respond(['ok'=>true,'module_code'=>$code,'registered'=>count($criteria)]);
 }
 if ($route==='grading_policy' && $method==='GET') {
   require_auth(['admin','teacher']);$module=required_string($_GET,'module_code',40);
   respond(['ok'=>true,'module_code'=>$module,'weights'=>grading_policy_for((int)$u['school_id'],$module)]);
 }
 if ($route==='grading_policy' && $method==='POST') {
   require_auth(['admin','teacher']);$in=json_in();$module=required_string($in,'module_code',40);$w=$in['weights']??null;
   if(!is_array($w)||array_keys($w)!==['portafolio','prueba']
      ||!is_numeric($w['portafolio'])||!is_numeric($w['prueba']))fail(422,'Pesos incorrectos');
   $a=(float)$w['portafolio'];$b=(float)$w['prueba'];
   if($a<0||$a>1||$b<0||$b>1||abs($a+$b-1)>0.00001)fail(422,'Los pesos deben sumar exactamente 1');
   $weights=['portafolio'=>$a,'prueba'=>$b];
   $db->prepare('INSERT INTO grading_policies(school_id,module_code,weights_json,updated_by) VALUES(?,?,?,?) ON CONFLICT(school_id,module_code) DO UPDATE SET weights_json=excluded.weights_json,updated_by=excluded.updated_by,updated_at=CURRENT_TIMESTAMP')
     ->execute([$u['school_id'],$module,json_encode($weights,JSON_THROW_ON_ERROR),$u['id']]);
   respond(['ok'=>true,'module_code'=>$module,'weights'=>$weights]);
 }
 if ($route==='grade_history' && $method==='GET') {
   require_auth(['admin','teacher']);$sid=(int)($_GET['submission_id']??0);
   $target=fetch_one('SELECT a.group_id FROM submissions s JOIN assignments a ON a.id=s.assignment_id WHERE s.id=?',[$sid]);
   if(!$target)fail(404,'Entrega no encontrada');teacher_group((int)$target['group_id'],$u);
   $rows=fetch_all('SELECT h.id,h.criterion_code,h.instrument,h.previous_score,h.new_score,h.created_at,t.display_name AS teacher_name FROM grade_history h JOIN users t ON t.id=h.teacher_id WHERE h.submission_id=? ORDER BY h.id DESC',[$sid]);
   respond(['ok'=>true,'items'=>$rows]);
 }

 if ($route==='users' && $method==='POST') {
   require_auth(['admin']);$in=json_in();$name=required_string($in,'name',180);
   $email=strtolower(required_string($in,'email',240));$password=required_string($in,'password',500);
   $role=required_string($in,'role',20);
   if (!in_array($role,['teacher','student','admin'],true) || strlen($password)<12) fail(422,'Rol o contraseña incorrectos (mínimo 12 caracteres)');
   try{$db->prepare('INSERT INTO users(school_id,email,display_name,role,passhash) VALUES(?,?,?,?,?)')->execute([$u['school_id'],$email,$name,$role,password_hash($password,PASSWORD_DEFAULT)]);$uid=(int)$db->lastInsertId();$db->prepare('INSERT INTO password_flags(user_id,must_change) VALUES(?,1)')->execute([$uid]);}
   catch(PDOException $e){fail(409,'El correo ya existe');}
   respond(['ok'=>true,'user_id'=>(int)$db->lastInsertId()],201);
 }
 if ($route==='users' && $method==='GET') {
   require_auth(['admin','teacher']);
   $rows=fetch_all('SELECT id,display_name,email,role FROM users WHERE school_id=? AND active=1 ORDER BY role,display_name',[$u['school_id']]);
   if ($u['role']==='teacher') $rows=array_values(array_filter($rows,fn($x)=>$x['role']==='student'));
   respond(['ok'=>true,'items'=>$rows]);
 }
 if ($route==='groups' && $method==='POST') {
   require_auth(['admin','teacher']);$in=json_in();
   $name=required_string($in,'name',140);$year=required_string($in,'academic_year',24);
   $teacherId=$u['role']==='admin' ? (int)($in['teacher_id']??$u['id']) : (int)$u['id'];
   $teacher=fetch_one("SELECT id FROM users WHERE id=? AND school_id=? AND role IN ('teacher','admin')",[$teacherId,$u['school_id']]);
   if (!$teacher) fail(403,'Profesor no autorizado');
   try{$db->prepare('INSERT INTO groups(school_id,name,academic_year,teacher_id) VALUES(?,?,?,?)')->execute([$u['school_id'],$name,$year,$teacherId]);}
   catch(PDOException $e){fail(409,'Ese grupo ya existe en el curso académico');}
   respond(['ok'=>true,'group_id'=>(int)$db->lastInsertId()],201);
 }
 if ($route==='groups' && $method==='GET') {
   if ($u['role']==='student') $rows=fetch_all('SELECT g.id,g.name,g.academic_year FROM groups g JOIN enrollments e ON e.group_id=g.id AND e.student_id=?',[$u['id']]);
   else $rows=fetch_all('SELECT g.id,g.name,g.academic_year,g.teacher_id FROM groups g WHERE g.school_id=?'.($u['role']==='teacher'?' AND g.teacher_id=?':'').' ORDER BY g.academic_year DESC,g.name',$u['role']==='teacher'?[$u['school_id'],$u['id']]:[$u['school_id']]);
   respond(['ok'=>true,'items'=>$rows]);
 }
 if ($route==='enroll' && $method==='POST') {
   require_auth(['admin','teacher']);$in=json_in();$gid=(int)($in['group_id']??0);teacher_group($gid,$u);
   $student=fetch_one("SELECT id FROM users WHERE school_id=? AND email=? AND role='student' AND active=1",[$u['school_id'],strtolower(required_string($in,'student_email',240))]);
   if (!$student) fail(404,'Alumno no encontrado en el centro');
   $db->prepare('INSERT OR IGNORE INTO enrollments(group_id,student_id) VALUES(?,?)')->execute([$gid,$student['id']]);
   respond(['ok'=>true]);
 }
 if ($route==='library' && $method==='POST') {
   require_auth(['admin','teacher']);$in=json_in();
   $title=required_string($in,'title',220);$module=required_string($in,'module_code',40);
   $external=required_string($in,'external_id',140);$curriculum=(string)($in['curriculum']??'');
   if (strlen($curriculum)>1000) fail(422,'Currículo demasiado largo');
   $criteria=$in['criteria']??[];
   if (!is_array($criteria) || count($criteria)>300) fail(422,'Criterios incorrectos');
   $seen=[];
   foreach($criteria as $c){
     if(!is_array($c)||!isset($c['code'],$c['ra'])||!is_string($c['code'])||!is_string($c['ra'])||!preg_match('/^RA[0-9]+\.[a-z]$/',$c['code'])||!preg_match('/^RA[0-9]+$/',$c['ra'])||!str_starts_with($c['code'],$c['ra'].'.') || isset($seen[$c['code']]))fail(422,'RA/CE inválido o duplicado');
     $seen[$c['code']]=true;
   }
   $curriculumVerified=require_curriculum_criteria((int)$u['school_id'],$module,$criteria);
   if(!$curriculumVerified && (bool)(cfg()['require_curriculum_catalog']??false))fail(422,'Falta incorporar el currículo oficial validado de este módulo');
   $raw=required_string($in,'zip_base64',(int)ceil((int)cfg()['max_package_bytes']*1.4)+50);
   $binary=base64_decode($raw,true);if($binary===false || strlen($binary)<20 || strlen($binary)>(int)cfg()['max_package_bytes'] || substr($binary,0,2)!=='PK')fail(422,'ZIP de alumnado inválido o demasiado grande');
   if(!class_exists('ZipArchive'))fail(503,'La extensión PHP ZipArchive es necesaria para validar paquetes');
   $tmp=tempnam(sys_get_temp_dir(),'cfp');if($tmp===false)fail(500,'No se pudo crear archivo temporal');
   try{
    file_put_contents($tmp,$binary);$zip=new ZipArchive();
    if($zip->open($tmp)!==true)fail(422,'ZIP ilegible');
    if($zip->numFiles>1200)fail(422,'ZIP con demasiados archivos');
    for($i=0;$i<$zip->numFiles;$i++){
      $item=$zip->getNameIndex($i);
      if(!$item || str_contains($item,'..') || str_starts_with($item,'/') || preg_match('/(^|\/)(docente|soluciones)(\/|$)/i',$item))fail(422,'Ruta insegura o material docente detectado');
    }
    $contents=$zip->getFromName('manifest.json');
    if($contents===false || strlen($contents)>2*1024*1024)fail(422,'Falta el manifiesto del paquete');
    $manifest=json_decode($contents,true);
    if(!is_array($manifest) || ($manifest['schemaId']??'')!=='contafp360.alumno.v1'||(string)($manifest['id']??'')!==$external)fail(422,'El manifiesto no corresponde al supuesto indicado');
    foreach(['soluciones','respuestasCorrectas','asientosSolucion','profesor'] as $forbidden) if(array_key_exists($forbidden,$manifest))fail(422,'El paquete contiene datos reservados al profesor');
    $zip->close();
   } finally { @unlink($tmp); }
   $dir=cfg()['upload_dir'];if(!is_dir($dir) && !mkdir($dir,0700,true) && !is_dir($dir))fail(500,'No se pudo crear el almacén');
   $hash=hash('sha256',$binary);$file=$dir.'/'.$hash.'.zip';
   if(!is_file($file) && file_put_contents($file,$binary,LOCK_EX)!==strlen($binary)) fail(500,'No se pudo guardar el paquete');
   $revision=(int)($in['revision']??1);
   if($revision<1 || $revision>100000) fail(422,'Revisión incorrecta');
   // Reintentos idempotentes: si el servidor guardó el ZIP pero se perdió la respuesta,
   // devolver el identificador existente, nunca bloquear la cola del profesor.
   $criteriaJson=json_encode($criteria,JSON_THROW_ON_ERROR);
   $samePublication=static function(?array $existing) use ($u,$hash,$title,$module,$curriculum,$criteriaJson): bool {
     return $existing!==null && (int)$existing['teacher_id']===(int)$u['id']
       && hash_equals($existing['sha256'],$hash)
       && $existing['title']===$title && $existing['module_code']===$module
       && $existing['curriculum']===$curriculum && $existing['criteria_json']===$criteriaJson;
   };
   $existing=fetch_one('SELECT id,teacher_id,sha256,title,module_code,curriculum,criteria_json FROM exercises WHERE school_id=? AND external_id=? AND revision=?',[$u['school_id'],$external,$revision]);
   if($existing) {
     if(!$samePublication($existing))fail(409,'Revisión en uso con distinto contenido: incremente la revisión');
     respond(['ok'=>true,'exercise_id'=>(int)$existing['id'],'sha256'=>$hash,'already_received'=>true]);
   }
   try {
     $db->prepare('INSERT INTO exercises(school_id,teacher_id,external_id,revision,title,module_code,curriculum,criteria_json,manifest_json,zip_path,sha256) VALUES(?,?,?,?,?,?,?,?,?,?,?)')
       ->execute([$u['school_id'],$u['id'],$external,$revision,$title,$module,$curriculum,$criteriaJson,$contents,$file,$hash]);
   } catch(PDOException $e) {
     // Otra petición idéntica pudo terminar durante el INSERT.
     $existing=fetch_one('SELECT id,teacher_id,sha256,title,module_code,curriculum,criteria_json FROM exercises WHERE school_id=? AND external_id=? AND revision=?',[$u['school_id'],$external,$revision]);
     if(!$samePublication($existing))fail(409,'Revisión en uso con distinto contenido: incremente la revisión');
     respond(['ok'=>true,'exercise_id'=>(int)$existing['id'],'sha256'=>$hash,'already_received'=>true]);
   }
   respond(['ok'=>true,'exercise_id'=>(int)$db->lastInsertId(),'sha256'=>$hash,'already_received'=>false],201);
 }
 if ($route==='library' && $method==='GET') {
   require_auth(['admin','teacher']);$rows=fetch_all('SELECT id,external_id,revision,title,module_code,curriculum,criteria_json,created_at FROM exercises WHERE school_id=? ORDER BY created_at DESC,id DESC',[$u['school_id']]);
   foreach($rows as &$x){$x['criteria']=json_decode($x['criteria_json'],true);$x['curriculum_verified']=curriculum_catalog_for((int)$u['school_id'],$x['module_code'])!==null;unset($x['criteria_json']);}
   respond(['ok'=>true,'items'=>$rows]);
 }
 if ($route==='assign' && $method==='POST') {
   require_auth(['admin','teacher']);$in=json_in();$gid=(int)($in['group_id']??0);$eid=(int)($in['exercise_id']??0);
   teacher_group($gid,$u);
   $exercise=fetch_one('SELECT id FROM exercises WHERE id=? AND school_id=?',[$eid,$u['school_id']]);if(!$exercise)fail(404,'Ejercicio no encontrado');
   $attempts=(int)($in['max_attempts']??3);if($attempts<1 || $attempts>100)fail(422,'Intentos incorrectos');
   $due=$in['due_at']??null;
   if($due!==null && (!is_string($due)||!preg_match('/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/',$due)))fail(422,'Fecha UTC no válida');
   $existing=fetch_one('SELECT * FROM assignments WHERE group_id=? AND exercise_id=?',[$gid,$eid]);
   if($existing) {
     if((int)$existing['max_attempts']!==$attempts || $existing['due_at']!==$due)fail(409,'La asignación existente tiene parámetros diferentes');
     respond(['ok'=>true,'assignment_id'=>(int)$existing['id'],'already_received'=>true]);
   }
   try {
     $db->prepare('INSERT INTO assignments(group_id,exercise_id,assigned_by,due_at,max_attempts) VALUES(?,?,?,?,?)')
        ->execute([$gid,$eid,$u['id'],$due,$attempts]);
   } catch(PDOException $e) {
     $existing=fetch_one('SELECT * FROM assignments WHERE group_id=? AND exercise_id=?',[$gid,$eid]);
     if(!$existing || (int)$existing['max_attempts']!==$attempts || $existing['due_at']!==$due)fail(409,'Asignación existente incompatible');
     respond(['ok'=>true,'assignment_id'=>(int)$existing['id'],'already_received'=>true]);
   }
   respond(['ok'=>true,'assignment_id'=>(int)$db->lastInsertId(),'already_received'=>false],201);
 }
 if ($route==='pull' && $method==='GET') {
   if ($u['role']==='student') {
     $rows=fetch_all('SELECT a.id AS assignment_id,a.due_at,a.max_attempts,e.id AS exercise_id,e.title,e.external_id,e.revision,e.module_code,e.criteria_json,e.sha256 FROM assignments a JOIN enrollments en ON en.group_id=a.group_id AND en.student_id=? JOIN exercises e ON e.id=a.exercise_id ORDER BY a.id DESC',[$u['id']]);
   } else {
     $rows=fetch_all('SELECT a.id AS assignment_id,a.due_at,a.max_attempts,e.id AS exercise_id,e.title,e.external_id,e.revision,e.module_code,e.criteria_json,e.sha256,g.name AS group_name FROM assignments a JOIN groups g ON g.id=a.group_id JOIN exercises e ON e.id=a.exercise_id WHERE g.school_id=?'.($u['role']==='teacher'?' AND g.teacher_id=?':'').' ORDER BY a.id DESC',$u['role']==='teacher'?[$u['school_id'],$u['id']]:[$u['school_id']]);
   }
   foreach($rows as &$x){$x['criteria']=json_decode($x['criteria_json'],true);unset($x['criteria_json']);}
   respond(['ok'=>true,'items'=>$rows]);
 }
 if ($route==='package' && $method==='GET') {
   $exerciseId=(int)($_GET['id']??0);
   if ($u['role']==='student') {
     $row=fetch_one('SELECT e.* FROM exercises e JOIN assignments a ON a.exercise_id=e.id JOIN enrollments en ON en.group_id=a.group_id AND en.student_id=? WHERE e.id=? AND e.school_id=? LIMIT 1',[$u['id'],$exerciseId,$u['school_id']]);
   } else {
     $row=fetch_one('SELECT * FROM exercises WHERE id=? AND school_id=?',[$exerciseId,$u['school_id']]);
   }
   if (!$row || !is_file($row['zip_path']))fail(404,'Paquete no disponible');
   header('Content-Type: application/zip');header('Content-Disposition: attachment; filename="CONTA-FP360-alumnado.zip"');header('X-Content-Type-Options: nosniff');
   header('Cache-Control: private, no-store');header('Content-Length: '.filesize($row['zip_path']));
   readfile($row['zip_path']);exit;
 }
 if ($route==='submit' && $method==='POST') {
   require_auth(['student']);$in=json_in();$aid=(int)($in['assignment_id']??0);$assignment=student_assigned($aid,$u);
   $event=required_string($in,'event_id',120);
   if(!preg_match('/^[a-zA-Z0-9_-]{12,120}$/',$event))fail(422,'Identificador de entrega incorrecto');
   $attempt=(int)($in['attempt']??0);if($attempt<1 || $attempt>(int)$assignment['max_attempts'])fail(422,'Intento fuera del límite permitido');
   // Una entrega sincronizada tarde se acepta pero queda marcada para revisión docente.
   $late=($assignment['due_at'] && gmdate('Y-m-d\TH:i:s\Z')>$assignment['due_at']) ? 1 : 0;
   $work=$in['work']??null;
   if(!is_array($work)||array_is_list($work))fail(422,'Trabajo incorrecto');
   $json=json_encode($work,JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR);
   if(strlen($json)>(int)cfg()['max_submission_bytes'])fail(413,'Trabajo demasiado grande');
   $payloadHash=hash('sha256',$json);
   $existing=fetch_one('SELECT id,student_id,assignment_id,attempt,payload_sha256,late FROM submissions WHERE event_id=?',[$event]);
   if($existing){
     if((int)$existing['student_id']!==(int)$u['id'] || (int)$existing['assignment_id']!==$aid || (int)$existing['attempt']!==$attempt || !hash_equals($existing['payload_sha256'],$payloadHash)) fail(409,'Identificador de entrega utilizado con distinto contenido');
     respond(['ok'=>true,'submission_id'=>(int)$existing['id'],'already_received'=>true,'late'=>(bool)$existing['late']]);
   }
   try{$db->prepare('INSERT INTO submissions(assignment_id,student_id,attempt,event_id,payload_json,payload_sha256,late) VALUES(?,?,?,?,?,?,?)')->execute([$aid,$u['id'],$attempt,$event,$json,$payloadHash,$late]);}
   catch(PDOException $e){fail(409,'El intento ya fue recibido; utilice otro número de intento');}
   respond(['ok'=>true,'submission_id'=>(int)$db->lastInsertId(),'already_received'=>false,'late'=>(bool)$late],201);
 }
 if ($route==='submissions' && $method==='GET') {
   require_auth(['admin','teacher']);$gid=(int)($_GET['group_id']??0);teacher_group($gid,$u);
   $rows=fetch_all('SELECT s.id,s.assignment_id,s.student_id,s.attempt,s.late,s.received_at,s.payload_sha256,u.display_name,e.title,e.criteria_json FROM submissions s JOIN assignments a ON a.id=s.assignment_id JOIN exercises e ON e.id=a.exercise_id JOIN users u ON u.id=s.student_id WHERE a.group_id=? ORDER BY s.received_at DESC,s.id DESC',[$gid]);
   foreach($rows as &$row){$row['criteria']=json_decode($row['criteria_json'],true);unset($row['criteria_json']);}
   respond(['ok'=>true,'items'=>$rows]);
 }
 if ($route==='submission' && $method==='GET') {
   require_auth(['admin','teacher']);$sid=(int)($_GET['id']??0);
   $row=fetch_one('SELECT s.*,a.group_id FROM submissions s JOIN assignments a ON a.id=s.assignment_id WHERE s.id=?',[$sid]);if(!$row)fail(404,'Entrega no encontrada');teacher_group((int)$row['group_id'],$u);
   $row['work']=json_decode($row['payload_json'],true);unset($row['payload_json']);
   respond(['ok'=>true,'item'=>$row]);
 }
 if ($route==='grade' && $method==='POST') {
   require_auth(['admin','teacher']);$in=json_in();$sid=(int)($in['submission_id']??0);
   $sub=fetch_one('SELECT s.id,a.group_id,e.criteria_json FROM submissions s JOIN assignments a ON a.id=s.assignment_id JOIN exercises e ON e.id=a.exercise_id WHERE s.id=?',[$sid]);
   if(!$sub)fail(404,'Entrega no encontrada');teacher_group((int)$sub['group_id'],$u);
   $allowed=criteria_for($sub);$grades=$in['grades']??null;
   if(!is_array($grades)||count($grades)>600)fail(422,'Calificaciones incorrectas');
   $db->beginTransaction();
   try{
     $stmt=$db->prepare('INSERT INTO grades(submission_id,criterion_code,instrument,score,teacher_id) VALUES(?,?,?,?,?) ON CONFLICT(submission_id,criterion_code,instrument) DO UPDATE SET score=excluded.score,teacher_id=excluded.teacher_id,updated_at=CURRENT_TIMESTAMP');
     $audit=$db->prepare('INSERT INTO grade_history(submission_id,criterion_code,instrument,previous_score,new_score,teacher_id) VALUES(?,?,?,?,?,?)');
     foreach($grades as $g){
       if(!is_array($g)||!isset($g['criterion_code'],$g['instrument'],$g['score']))fail(422,'Calificación incompleta');
       $code=(string)$g['criterion_code'];$instrument=(string)$g['instrument'];$score=$g['score'];
       if(!isset($allowed[$code])||!in_array($instrument,['portafolio','prueba'],true)||!is_numeric($score)||$score<0||$score>10)fail(422,'Calificación no permitida');
       $previous=fetch_one('SELECT score FROM grades WHERE submission_id=? AND criterion_code=? AND instrument=?',[$sid,$code,$instrument]);
       if($previous===null || abs((float)$previous['score']-(float)$score)>0.000001) {
         $audit->execute([$sid,$code,$instrument,$previous!==null?(float)$previous['score']:null,(float)$score,$u['id']]);
         $stmt->execute([$sid,$code,$instrument,(float)$score,$u['id']]);
       }
     }
     $db->commit();
   } catch(Throwable $e){if($db->inTransaction())$db->rollBack();throw $e;}
   respond(['ok'=>true,'graded'=>count($grades)]);
 }
 if ($route==='report' && $method==='GET') {
   require_auth(['admin','teacher']);$gid=(int)($_GET['group_id']??0);teacher_group($gid,$u);
   $students=fetch_all('SELECT u.id,u.display_name FROM users u JOIN enrollments en ON en.student_id=u.id WHERE en.group_id=? ORDER BY u.display_name',[$gid]);
   $assignments=fetch_all('SELECT a.id,e.title,e.module_code,e.criteria_json FROM assignments a JOIN exercises e ON e.id=a.exercise_id WHERE a.group_id=? ORDER BY a.id',[$gid]);
   foreach($assignments as &$a){$a['criteria']=json_decode($a['criteria_json'],true);unset($a['criteria_json']);}
   $all=fetch_all('SELECT s.id,s.student_id,s.assignment_id,s.attempt,g.criterion_code,g.instrument,g.score FROM submissions s JOIN assignments a ON a.id=s.assignment_id LEFT JOIN grades g ON g.submission_id=s.id WHERE a.group_id=? ORDER BY s.student_id,s.assignment_id,s.attempt DESC,s.id DESC',[$gid]);
   $chosen=[];
   foreach($all as $x){$key=$x['student_id'].':'.$x['assignment_id'];if(!isset($chosen[$key]))$chosen[$key]=['submission_id'=>(int)$x['id'],'attempt'=>(int)$x['attempt'],'scores'=>[]];if((int)$chosen[$key]['submission_id']===(int)$x['id'] && $x['criterion_code']!==null)$chosen[$key]['scores'][$x['criterion_code']][$x['instrument']]=(float)$x['score'];}
   $matrix=[];
   foreach($students as $student){
     $row=['student_id'=>(int)$student['id'],'name'=>$student['display_name'],'assignments'=>[]];
     foreach($assignments as $a){
       $weight=grading_policy_for((int)$u['school_id'],(string)$a['module_code']);
       $entry=$chosen[$student['id'].':'.$a['id']]??null;$scores=[];$ra=[];
       foreach($a['criteria'] as $c){$code=$c['code'];$instrumentScores=$entry['scores'][$code]??[];
         // 60/40 SOLO cuando ambos instrumentos cuentan con calificación confirmada.
         $complete=true;$value=0.0;
         foreach($weight as $instrument=>$factor) {
           if($factor>0 && !isset($instrumentScores[$instrument])){$complete=false;break;}
           if($factor>0)$value+=$factor*$instrumentScores[$instrument];
         }
         $value=$complete?round($value,2):null;
         $scores[$code]=['instruments'=>$instrumentScores,'final'=>$value,'complete'=>$value!==null];
         if($value!==null)$ra[$c['ra']][]=$value;
       }
       $ras=[];foreach($ra as $code=>$values){$expected=count(array_filter($a['criteria'],fn($x)=>$x['ra']===$code));$ras[$code]=['score'=>count($values)===$expected?round(array_sum($values)/count($values),2):null,'graded'=>count($values),'total'=>$expected];}
       $row['assignments'][]=['assignment_id'=>(int)$a['id'],'title'=>$a['title'],'grading_weights'=>$weight,'submission'=>$entry?['submission_id'=>$entry['submission_id'],'attempt'=>$entry['attempt']]:null,'criteria'=>$scores,'ra'=>$ras];
     }
     $matrix[]=$row;
   }
   respond(['ok'=>true,'group_id'=>$gid,'grading_weights'=>['portafolio'=>0.6,'prueba'=>0.4],'students'=>$matrix]);
 }
 fail(404,'Ruta inexistente');
} catch(Throwable $e){
 error_log('[CONTA FP360 Central] '.$e->getMessage());fail(500,'Error interno del servidor');
}
