<?php
declare(strict_types=1);
/**
 * Migraciones aditivas de Central. No modifica las tablas históricas ni pierde notas.
 * Se ejecuta automáticamente tras conectar a SQLite; compatible con instalaciones 2.3.
 */
function ensure_central_features(PDO $db): void {
  $db->exec(<<<'SQL'
CREATE TABLE IF NOT EXISTS password_flags(
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  must_change INTEGER NOT NULL DEFAULT 1 CHECK(must_change IN (0,1)),
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS grade_history(
  id INTEGER PRIMARY KEY,
  submission_id INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
  criterion_code TEXT NOT NULL, instrument TEXT NOT NULL,
  previous_score REAL, new_score REAL NOT NULL CHECK(new_score BETWEEN 0 AND 10),
  teacher_id INTEGER NOT NULL REFERENCES users(id),
  action TEXT NOT NULL DEFAULT 'set',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_grade_history_submission ON grade_history(submission_id,id);
CREATE TABLE IF NOT EXISTS grading_policies(
  school_id INTEGER NOT NULL REFERENCES schools(id),
  module_code TEXT NOT NULL,
  weights_json TEXT NOT NULL,
  updated_by INTEGER NOT NULL REFERENCES users(id),
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(school_id,module_code)
);
CREATE TABLE IF NOT EXISTS curriculum_catalogs(
  school_id INTEGER NOT NULL REFERENCES schools(id),
  module_code TEXT NOT NULL,
  territory TEXT NOT NULL,
  source_url TEXT NOT NULL,
  version TEXT NOT NULL,
  criteria_json TEXT NOT NULL,
  updated_by INTEGER NOT NULL REFERENCES users(id),
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(school_id,module_code)
);
CREATE TABLE IF NOT EXISTS teacher_licenses(
  id INTEGER PRIMARY KEY,
  teacher_id INTEGER NOT NULL REFERENCES users(id),
  classroom_limit INTEGER NOT NULL CHECK(classroom_limit BETWEEN 1 AND 10000),
  unit_price_cents INTEGER NOT NULL DEFAULT 1000 CHECK(unit_price_cents=1000),
  starts_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL CHECK(expires_at>starts_at),
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','revoked')),
  source_ref TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_teacher_licenses_owner
  ON teacher_licenses(teacher_id,status,expires_at);
CREATE TABLE IF NOT EXISTS license_classrooms(
  group_id INTEGER PRIMARY KEY REFERENCES groups(id),
  license_id INTEGER NOT NULL REFERENCES teacher_licenses(id),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_license_classrooms_license
  ON license_classrooms(license_id);
SQL);
}

/**
 * Activates a verified annual entitlement. Payment callbacks must call this only
 * after independently verifying the payment with the provider.
 */
function activate_teacher_license(PDO $db,int $teacherId,int $classrooms,string $sourceRef,int $paidAt): array {
  if($teacherId<1 || $classrooms<1 || $classrooms>10000 ||
     trim($sourceRef)==='' || strlen($sourceRef)>200 || $paidAt<1)
    throw new InvalidArgumentException('Datos de licencia incorrectos');
  $teacher=$db->prepare("SELECT id FROM users WHERE id=? AND role='teacher' AND active=1");
  $teacher->execute([$teacherId]);
  if(!$teacher->fetch())throw new InvalidArgumentException('La licencia debe pertenecer a una cuenta docente activa');
  $existing=$db->prepare('SELECT id,teacher_id,classroom_limit,starts_at,expires_at FROM teacher_licenses WHERE source_ref=?');
  $existing->execute([$sourceRef]);
  $row=$existing->fetch();
  if($row){
    if((int)$row['teacher_id']!==$teacherId || (int)$row['classroom_limit']!==$classrooms ||
       (int)$row['expires_at']<=(int)$row['starts_at'])
      throw new RuntimeException('La referencia de pago ya está vinculada a otra licencia');
    return $row;
  }
  $start=(new DateTimeImmutable('@'.$paidAt))->setTimezone(new DateTimeZone('UTC'));
  $expires=$start->modify('+1 year');
  $insert=$db->prepare('INSERT INTO teacher_licenses(teacher_id,classroom_limit,starts_at,expires_at,source_ref) VALUES(?,?,?,?,?)');
  $insert->execute([$teacherId,$classrooms,$paidAt,$expires->getTimestamp(),$sourceRef]);
  return ['id'=>(int)$db->lastInsertId(),'teacher_id'=>$teacherId,'classroom_limit'=>$classrooms,
    'starts_at'=>$paidAt,'expires_at'=>$expires->getTimestamp()];
}

/** Assign the new group to an active, unexpired annual classroom slot. */
function allocate_licensed_classroom(PDO $db,int $groupId,int $teacherId,int $now): bool {
  $stmt=$db->prepare(<<<'SQL'
SELECT l.id
FROM teacher_licenses l
WHERE l.teacher_id=? AND l.status='active' AND l.starts_at<=? AND l.expires_at>?
  AND (SELECT COUNT(*) FROM license_classrooms lc WHERE lc.license_id=l.id)<l.classroom_limit
ORDER BY l.expires_at,l.id
SQL);
  $stmt->execute([$teacherId,$now,$now]);
  $licenseId=$stmt->fetchColumn();
  if($licenseId===false)return false;
  $insert=$db->prepare('INSERT INTO license_classrooms(group_id,license_id) VALUES(?,?)');
  $insert->execute([$groupId,(int)$licenseId]);
  return true;
}

/**
 * Existing groups have no license link and remain in legacy mode. Licensed
 * groups stop server synchronization when their own teacher's term is inactive.
 */
function require_classroom_license(int $groupId): void {
  $row=fetch_one(<<<'SQL'
SELECT l.status,l.starts_at,l.expires_at
FROM license_classrooms lc
JOIN teacher_licenses l ON l.id=lc.license_id
JOIN groups g ON g.id=lc.group_id AND g.teacher_id=l.teacher_id
WHERE lc.group_id=?
SQL,[$groupId]);
  if(!$row)return;
  $now=time();
  if($row['status']!=='active' || (int)$row['starts_at']>$now || (int)$row['expires_at']<=$now)
    fail(403,'La licencia anual de esta aula no está activa. Los trabajos locales se conservan; renueve la licencia para sincronizar.');
}

function teacher_license_status(int $teacherId): array {
  $now=time();
  $licenses=fetch_all(<<<'SQL'
SELECT l.id,l.classroom_limit,l.unit_price_cents,l.starts_at,l.expires_at,l.status,
       (SELECT COUNT(*) FROM license_classrooms lc WHERE lc.license_id=l.id) AS used_classrooms
FROM teacher_licenses l
WHERE l.teacher_id=?
ORDER BY l.starts_at DESC,l.id DESC
SQL,[$teacherId]);
  $activeLimit=0;$activeUsed=0;
  foreach($licenses as &$license){
    $license['id']=(int)$license['id'];
    $license['classroom_limit']=(int)$license['classroom_limit'];
    $license['unit_price_cents']=(int)$license['unit_price_cents'];
    $license['used_classrooms']=(int)$license['used_classrooms'];
    $license['starts_at']=(int)$license['starts_at'];
    $license['expires_at']=(int)$license['expires_at'];
    $license['state']=$license['status']!=='active'?'revoked':
      ($license['starts_at']>$now?'pending':($license['expires_at']<=$now?'expired':'active'));
    if($license['state']==='active'){
      $activeLimit+=$license['classroom_limit'];
      $activeUsed+=$license['used_classrooms'];
    }
  }
  unset($license);
  $legacy=fetch_one(<<<'SQL'
SELECT COUNT(*) AS total FROM groups g
WHERE g.teacher_id=? AND NOT EXISTS(
  SELECT 1 FROM license_classrooms lc WHERE lc.group_id=g.id
)
SQL,[$teacherId]);
  return [
    'price_per_classroom_year_eur'=>10,
    'active_classrooms'=>$activeUsed,
    'classroom_limit'=>$activeLimit,
    'available_classrooms'=>max(0,$activeLimit-$activeUsed),
    'legacy_classrooms'=>(int)($legacy['total']??0),
    'licenses'=>$licenses,
  ];
}

function grading_policy_for(int $schoolId,string $module): array {
  $found=fetch_one('SELECT weights_json FROM grading_policies WHERE school_id=? AND module_code=?',[$schoolId,$module]);
  $weights=$found?json_decode($found['weights_json'],true):null;
  return is_array($weights)?$weights:['portafolio'=>0.6,'prueba'=>0.4];
}
function curriculum_catalog_for(int $schoolId,string $module): ?array {
  $row=fetch_one('SELECT module_code,territory,source_url,version,criteria_json FROM curriculum_catalogs WHERE school_id=? AND module_code=?',[$schoolId,$module]);
  if(!$row)return null;
  $row['criteria']=json_decode($row['criteria_json'],true)??[];
  unset($row['criteria_json']);
  return $row;
}
function require_curriculum_criteria(int $schoolId,string $module,array $provided): bool {
  $catalog=curriculum_catalog_for($schoolId,$module);
  if(!$catalog)return false;
  $allowed=array_fill_keys($catalog['criteria'],true);
  foreach($provided as $c)if(!isset($allowed[$c['code']??'']))fail(422,'El criterio RA/CE no figura en el catálogo oficial de este módulo');
  return true;
}
function secure_new_password(string $password): void {
  if(strlen($password)<12||strlen($password)>500)fail(422,'La contraseña debe contener entre 12 y 500 caracteres');
}
