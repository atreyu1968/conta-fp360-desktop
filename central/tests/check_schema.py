from pathlib import Path
import sqlite3
import tempfile
root=Path(__file__).resolve().parents[1]
schema=(root/'cpanel/schema.sql').read_text()
with tempfile.TemporaryDirectory() as folder:
    db=sqlite3.connect(Path(folder)/'test.sqlite3')
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript(schema)
    db.executescript(schema)
    tables={x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    required={'users','schools','groups','enrollments','exercises','assignments','submissions','grades','tokens','meta'}
    assert required.issubset(tables),required-tables
    db.execute("INSERT INTO schools(id,name) VALUES(1,'Centro Ficticio')")
    db.execute("INSERT INTO users(id,school_id,email,display_name,role,passhash) VALUES(1,1,'t@ejemplo.es','Docente','teacher','hash')")
    db.execute("INSERT INTO users(id,school_id,email,display_name,role,passhash) VALUES(2,1,'e@ejemplo.es','Alumno','student','hash')")
    db.execute("INSERT INTO groups(id,school_id,name,academic_year,teacher_id) VALUES(1,1,'GM2','2026-2027',1)")
    db.execute("INSERT INTO enrollments(group_id,student_id) VALUES(1,2)")
    try:
        db.execute("INSERT INTO enrollments(group_id,student_id) VALUES(1,2)")
        raise AssertionError('No se ha aplicado la clave compuesta de matrículas')
    except sqlite3.IntegrityError:pass
    try:
        db.execute("INSERT INTO users(school_id,email,display_name,role,passhash) VALUES(1,'x@ejemplo.es','Falso','owner','hash')")
        raise AssertionError('Se ha aceptado un rol inválido')
    except sqlite3.IntegrityError:pass
    db.execute("INSERT INTO exercises(id,school_id,teacher_id,external_id,title,module_code,criteria_json,manifest_json,zip_path,sha256) VALUES(1,1,1,'EX-1','Caso demo','0441','[{\"code\":\"RA1.a\",\"ra\":\"RA1\"}]','{}','/tmp/demo.zip','checksum')")
    db.execute("INSERT INTO assignments(id,group_id,exercise_id,assigned_by) VALUES(1,1,1,1)")
    db.execute("INSERT INTO submissions(id,assignment_id,student_id,attempt,event_id,payload_json,payload_sha256) VALUES(1,1,2,1,'uuid-abc','{}','checksum')")
    db.execute("INSERT INTO grades(submission_id,criterion_code,instrument,score,teacher_id) VALUES(1,'RA1.a','portafolio',8,1)")
    db.execute("INSERT INTO grades(submission_id,criterion_code,instrument,score,teacher_id) VALUES(1,'RA1.a','prueba',6,1)")
    grade=db.execute("SELECT SUM(CASE instrument WHEN 'portafolio' THEN score*.6 ELSE score*.4 END) FROM grades WHERE submission_id=1").fetchone()[0]
    assert abs(grade-7.2)<1e-6
    try:
        db.execute("INSERT INTO grades(submission_id,criterion_code,instrument,score,teacher_id) VALUES(1,'RA1.b','prueba',11,1)")
        raise AssertionError('Nota > 10 aceptada')
    except sqlite3.IntegrityError:pass
    print('OK: esquema SQLite, claves, roles, matrícula, integridad y nota ponderada')
