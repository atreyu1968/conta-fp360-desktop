PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS schools (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, school_id INTEGER NOT NULL REFERENCES schools(id),
 email TEXT NOT NULL UNIQUE COLLATE NOCASE,
 display_name TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','teacher','student')),
 passhash TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS tokens (
 hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 expires_at INTEGER NOT NULL, created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tokens_user ON tokens(user_id);
CREATE TABLE IF NOT EXISTS groups (
 id INTEGER PRIMARY KEY, school_id INTEGER NOT NULL REFERENCES schools(id),
 name TEXT NOT NULL, academic_year TEXT NOT NULL,
 teacher_id INTEGER NOT NULL REFERENCES users(id),
 UNIQUE(school_id,name,academic_year)
);
CREATE TABLE IF NOT EXISTS enrollments (
 group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
 student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 PRIMARY KEY(group_id,student_id)
);
CREATE TABLE IF NOT EXISTS exercises (
 id INTEGER PRIMARY KEY, school_id INTEGER NOT NULL REFERENCES schools(id),
 teacher_id INTEGER NOT NULL REFERENCES users(id),
 external_id TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1,
 title TEXT NOT NULL, module_code TEXT NOT NULL, curriculum TEXT NOT NULL DEFAULT '',
 criteria_json TEXT NOT NULL, manifest_json TEXT NOT NULL, zip_path TEXT NOT NULL,
 sha256 TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(school_id,external_id,revision)
);
CREATE TABLE IF NOT EXISTS assignments (
 id INTEGER PRIMARY KEY, group_id INTEGER NOT NULL REFERENCES groups(id),
 exercise_id INTEGER NOT NULL REFERENCES exercises(id),
 assigned_by INTEGER NOT NULL REFERENCES users(id),
 due_at TEXT, max_attempts INTEGER NOT NULL DEFAULT 3 CHECK(max_attempts BETWEEN 1 AND 100),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(group_id,exercise_id)
);
CREATE TABLE IF NOT EXISTS submissions (
 id INTEGER PRIMARY KEY, assignment_id INTEGER NOT NULL REFERENCES assignments(id),
 student_id INTEGER NOT NULL REFERENCES users(id),
 attempt INTEGER NOT NULL CHECK(attempt BETWEEN 1 AND 100),
 event_id TEXT NOT NULL UNIQUE, payload_json TEXT NOT NULL,
 payload_sha256 TEXT NOT NULL,
 late INTEGER NOT NULL DEFAULT 0 CHECK(late IN (0,1)),
 received_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(assignment_id,student_id,attempt)
);
CREATE TABLE IF NOT EXISTS grades (
 submission_id INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
 criterion_code TEXT NOT NULL, instrument TEXT NOT NULL CHECK(instrument IN ('portafolio','prueba')),
 score REAL NOT NULL CHECK(score BETWEEN 0 AND 10),
 teacher_id INTEGER NOT NULL REFERENCES users(id),
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(submission_id,criterion_code,instrument)
);
CREATE INDEX IF NOT EXISTS idx_submissions_scope ON submissions(assignment_id,student_id);
CREATE INDEX IF NOT EXISTS idx_assignments_group ON assignments(group_id);

CREATE TABLE IF NOT EXISTS auth_attempts (
 key_hash TEXT PRIMARY KEY, failures INTEGER NOT NULL, reset_after INTEGER NOT NULL
);
