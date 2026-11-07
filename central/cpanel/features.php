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
SQL);
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
