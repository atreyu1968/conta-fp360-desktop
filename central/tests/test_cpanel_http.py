"""Prueba integral por HTTP, requiere PHP pdo_sqlite y ZipArchive.

Ejecutar: python3 tests/test_cpanel_http.py desde la raíz de la entrega.
Nunca utiliza el alojamiento real ni datos personales.
"""
from __future__ import annotations
import base64
import io
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "cpanel"

def ok(cond: bool, msg: str):
    if not cond:
        raise AssertionError(msg)

def json_request(base, route, body=None, token=None, params=None, expected=200):
    url = base + "/api.php?" + urllib.parse.urlencode({"r": route, **(params or {})})
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            code = response.status
            raw = response.read()
    except urllib.error.HTTPError as error:
        code = error.code
        raw = error.read()
    ok(code == expected, f"{route}: código {code}, esperado {expected}: {raw[:250]}")
    if route == 'package' and expected == 200:
        ok(raw.startswith(b'PK'), 'La descarga no es ZIP')
        return raw
    data = json.loads(raw)
    ok(data.get('ok') == (code < 400), f"{route}: respuesta incoherente {data}")
    return data

def check_desktop_preflight(base):
    for origin in ('tauri://localhost','http://tauri.localhost','https://tauri.localhost',
                   'http://localhost:1420','http://127.0.0.1:1420'):
        req=urllib.request.Request(base+'/api.php?r=login',method='OPTIONS',headers={
            'Origin':origin,'Access-Control-Request-Method':'POST',
            'Access-Control-Request-Headers':'authorization,content-type'})
        with urllib.request.urlopen(req,timeout=10) as response:
            ok(response.status==204,'Preflight Tauri no devuelve 204')
            ok(response.headers.get('Access-Control-Allow-Origin')==origin,
               'Central no autoriza el origen de Tauri '+origin)
            ok('Authorization' in response.headers.get('Access-Control-Allow-Headers',''),
               'Central no autoriza el token de sesión de escritorio')
    req=urllib.request.Request(base+'/api.php?r=login',method='OPTIONS',headers={
        'Origin':'https://origen-no-autorizado.example','Access-Control-Request-Method':'POST'})
    with urllib.request.urlopen(req,timeout=10) as response:
        ok(response.headers.get('Access-Control-Allow-Origin') is None,
           'Central autoriza un origen web externo')

def makezip(external_id, unsafe=False, criteria=None):
    stream = io.BytesIO()
    manifest={'schemaId': 'contafp360.alumno.v1', 'id': external_id, 'documentos': []}
    if criteria is not None: manifest['evaluacionCurricular']={'criterios':criteria}
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.json', json.dumps(manifest))
        if unsafe: z.writestr('soluciones/instructor.txt', 'NO DEBERIA EXISTIR')
    return base64.b64encode(stream.getvalue()).decode()

def test_http(layout='cpanel'):
    assert SOURCE.joinpath('api.php').exists()
    with tempfile.TemporaryDirectory(prefix='cfp360-http-') as temp:
        dst = Path(temp) / 'www'
        home = Path(temp) / 'home'
        home.mkdir()
        shutil.copytree(SOURCE, dst)
        secret = 'secret-de-prueba-no-se-usa-en-produccion-0001'
        config = "<?php return " + php_config(dst, secret) + ";\n"
        if layout == 'cpanel':
            (dst/'config.php').write_text(config)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        base=f'http://127.0.0.1:{port}'
        env={**os.environ,'HOME':str(home)}
        command=['php','-S',f'127.0.0.1:{port}','-t',str(dst)]
        if layout == 'ubuntu':
            config_path=Path(temp)/'etc'/'config.php'
            setup=['php',str(SOURCE.parent/'ubuntu'/'setup.php'),
                   '--config='+str(config_path),'--data-dir='+str(Path(temp)/'data'),
                   '--base-url='+base,'--school=IES Centro de Pruebas',
                   '--name=Administración del centro','--email=admin@example.test','--password-stdin']
            initialized=subprocess.run(setup,input='AdminTestPass12345\n',text=True,capture_output=True)
            ok(initialized.returncode==0,'Falla la instalación CLI: '+initialized.stderr)
            ok(not (dst/'config.php').exists(),'La configuración no debe quedar en la carpeta pública')
            env['CONTA_CONFIG_FILE']=str(config_path)
            command.append(str(SOURCE.parent/'ubuntu'/'dev-router.php'))
        proc=subprocess.Popen(command,
                              env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            for attempt in range(80):
                try:
                    json_request(base,'health');break
                except Exception:
                    time.sleep(.1)
            else:raise AssertionError('No arranca PHP servidor')
            check_desktop_preflight(base)
            admin_email='admin@example.test'
            form = urllib.parse.urlencode({'secret':secret,'school':'IES Centro de Pruebas','name':'Administración del centro','email':admin_email,'password':'AdminTestPass12345'}).encode()
            if layout == 'cpanel':
                with urllib.request.urlopen(urllib.request.Request(base+'/install.php',data=form),timeout=12) as r:
                    body=r.read().decode()
                    ok('Servidor instalado' in body,'No se ha completado la instalación')
            else:
                for path in ('/install.php','/config.php','/schema.sql','/bootstrap.php','/features.php','/.htaccess','/private/'):
                    try:
                        urllib.request.urlopen(base+path,timeout=5)
                        raise AssertionError('Archivo privado accesible: '+path)
                    except urllib.error.HTTPError as error:
                        ok(error.code==404,'Protección inesperada: '+path)
                for path in ('/','/assets/dashboard.js','/assets/visual.css'):
                    with urllib.request.urlopen(base+path,timeout=5) as response:
                        ok(response.status==200,'Recurso público inaccesible: '+path)
            admin=json_request(base,'login',{'email':admin_email,'password':'AdminTestPass12345'})['token']
            teacher='teacher@example.test';student='student@example.test';other='other@example.test'
            for name,email,role in [('Profesora',teacher,'teacher'),('Alumno',student,'student'),('Otro profesor',other,'teacher')]:
                json_request(base,'users',{'name':name,'email':email,'role':role,'password':'StrongPass12345!'},admin,expected=201)
            # Cuentas creadas por el administrador deben cambiar la clave inicial.
            fresh={}
            for email in (teacher,student,other):
                login=json_request(base,'login',{'email':email,'password':'StrongPass12345!'})
                ok(login['user']['must_change_password'] is True,'La clave inicial no queda marcada como temporal')
                json_request(base,'groups',None,login['token'],expected=403)
                json_request(base,'change_password',{'current_password':'StrongPass12345!','new_password':'StrongNewPass9876!'},login['token'])
                json_request(base,'groups',None,login['token'],expected=401)
                fresh[email]=json_request(base,'login',{'email':email,'password':'StrongNewPass9876!'})['token']
            t=fresh[teacher];st=fresh[student];other_token=fresh[other]
            db_path=(home/'.conta-fp360'/'conta-central.sqlite3') if layout=='cpanel' else Path(temp)/'data'/'conta-central.sqlite3'
            paid_at=int(time.time())-60
            with sqlite3.connect(db_path) as connection:
                teacher_id=connection.execute("SELECT id FROM users WHERE email=?",(teacher,)).fetchone()[0]
                other_teacher_id=connection.execute("SELECT id FROM users WHERE email=?",(other,)).fetchone()[0]
                school_id=connection.execute("SELECT school_id FROM users WHERE id=?",(teacher_id,)).fetchone()[0]
                connection.execute(
                    "INSERT INTO teacher_licenses(teacher_id,classroom_limit,unit_price_cents,starts_at,expires_at,status,source_ref) VALUES(?,1,1000,?,?, 'active','fixture-payment-1')",
                    (teacher_id,paid_at,paid_at+365*24*60*60))
                connection.execute(
                    "INSERT INTO teacher_licenses(teacher_id,classroom_limit,unit_price_cents,starts_at,expires_at,status,source_ref) VALUES(?,1,1000,?,?, 'active','fixture-payment-2')",
                    (other_teacher_id,paid_at,paid_at+365*24*60*60))
                connection.execute(
                    "INSERT INTO groups(school_id,name,academic_year,teacher_id) VALUES(?,?,?,?)",
                    (school_id,'Aula histórica','2025-2026',teacher_id))
                legacy_group=connection.execute("SELECT last_insert_rowid()").fetchone()[0]
            license_status=json_request(base,'license',token=t)['license']
            ok(license_status['available_classrooms']==1 and license_status['legacy_classrooms']==1,
               'El estado de licencia/cupo o el tratamiento de aulas históricas es incorrecto')
            json_request(base,'license',token=st,expected=403)
            if layout == 'ubuntu':
                # La configuración Ubuntu exige catálogo desde el primer momento.
                json_request(base,'library',{'title':'Sin catálogo','external_id':'NO-CATALOG',
                    'module_code':'0441','criteria':[{'code':'RA4.a','ra':'RA4'}],
                    'zip_base64':makezip('NO-CATALOG')},t,expected=422)
                json_request(base,'curricula',{'module_code':'0441','territory':'Canarias',
                    'version':'prueba-esquema','source_url':'https://www.boe.es/buscar/act.php?id=BOE-A-2009-19148',
                    'criteria':['RA4.a','RA4.b']},admin)
            group=json_request(base,'groups',{'name':'2º GA','academic_year':'2026-2027'},t,expected=201)['group_id']
            json_request(base,'groups',{'name':'3º GA','academic_year':'2026-2027'},t,expected=403)
            json_request(base,'groups',None,st)
            json_request(base,'enroll',{'group_id':group,'student_email':student},t)
            json_request(base,'library',{},st,expected=403)
            identifier='CONTA-FP360-PRUEBA-001'
            publication={'title':'Compras y ventas con IGIC','external_id':identifier,'module_code':'0441','revision':1,'curriculum':'BOE-A-2009-19148','criteria':[{'code':'RA4.a','ra':'RA4'},{'code':'RA4.b','ra':'RA4'}],'zip_base64':makezip(identifier)}
            first=json_request(base,'library',publication,t,expected=201)
            exercise=first['exercise_id']
            retransmit=json_request(base,'library',publication,t)
            ok(retransmit['exercise_id']==exercise and retransmit['already_received'] is True,'Publicación no idempotente')
            json_request(base,'library',{**publication,'title':'Título modificado'},t,expected=409)
            json_request(base,'library',{'title':'X','external_id':'BAD-SOL','module_code':'0441','criteria':[],'zip_base64':makezip('BAD-SOL',True)},t,expected=422)
            # No admitir discrepancias entre CE publicados y los del manifiesto.
            json_request(base,'library',{**publication,'external_id':'BAD-CE-MISMATCH','zip_base64':makezip('BAD-CE-MISMATCH',criteria=['RA4.a'])},t,expected=422)
            unassigned_exercise=json_request(base,'library',{**publication,'external_id':'VALID-CE-MATCH','zip_base64':makezip('VALID-CE-MATCH',criteria=['RA4.a','RA4.b'])},t,expected=201)['exercise_id']
            assignment={'group_id':group,'exercise_id':exercise,'max_attempts':3,'due_at':'2020-01-01T00:00:00Z'}
            aid=json_request(base,'assign',assignment,t,expected=201)['assignment_id']
            redelivery=json_request(base,'assign',assignment,t)
            ok(redelivery['already_received'] and redelivery['assignment_id']==aid,'Asignación no idempotente')
            other_group=json_request(base,'groups',{'name':'Grupo de otra profesora','academic_year':'2026-2027'},other_token,expected=201)['group_id']
            other_exercise=json_request(base,'library',{**publication,'title':'Ejercicio de otra aula',
                'external_id':'CONTA-FP360-OTRA-AULA','zip_base64':makezip('CONTA-FP360-OTRA-AULA')},other_token,expected=201)['exercise_id']
            other_assignment=json_request(base,'assign',{'group_id':other_group,'exercise_id':other_exercise,
                'max_attempts':3},other_token,expected=201)['assignment_id']
            json_request(base,'report',None,st,{'group_id':group},expected=403)
            json_request(base,'report',None,other_token,{'group_id':group},expected=403)
            pulled=json_request(base,'pull',None,st)['items']
            ok(len(pulled)==1 and pulled[0]['assignment_id']==aid,'No llega la asignación al alumno')
            ok(pulled[0]['group_id']==group and pulled[0]['group_name']=='2º GA'
               and pulled[0]['academic_year']=='2026-2027' and pulled[0]['teacher_name']=='Profesora',
               'Aula no recibe el nombre y docente del grupo matriculado')
            ok(all(x['assignment_id']!=other_assignment for x in pulled),
               'Aula recibe una asignación del grupo donde el alumno no está matriculado')
            teacher_assignments=json_request(base,'pull',None,t)['items']
            ok(len(teacher_assignments)==1 and teacher_assignments[0]['group_id']==group,
               'Studio muestra asignaciones de otro profesor')
            pkg=json_request(base,'package',None,st,{'id':exercise});ok(len(pkg)>30,'Paquete corrupto')
            json_request(base,'package',None,st,{'id':other_exercise},expected=404)
            delivery={'assignment_id':aid,'attempt':1,'event_id':'TESTOFFLINE2026A1','work':{'manifest_id':identifier,'asientos':[{'id':'1','debe':500,'haber':500}]}}
            json_request(base,'submit',{**delivery,'event_id':'WRONGMANIFEST2026','work':{'manifest_id':'OTRO-SUPUESTO','asientos':[{'id':'1'}]}},st,expected=422)
            accepted=json_request(base,'submit',delivery,st,expected=201)
            subsequent=json_request(base,'pull',None,st)['items']
            ok(next(x['used_attempts'] for x in subsequent if x['assignment_id']==aid)==1,
               'El servidor no comunica los intentos ya sincronizados a otro equipo')
            ok(accepted['late'] is True,'No se ha marcado como tardía una entrega offline recibida fuera del plazo')
            repeated=json_request(base,'submit',delivery,st)
            ok(repeated['already_received'] is True and repeated['submission_id']==accepted['submission_id'],'Reintento no idempotente')
            bad={**delivery,'work':{'manifest_id':identifier,'asientos':[{'id':1,'debe':999}]}}
            json_request(base,'submit',bad,st,expected=409)
            badattempt={**delivery,'event_id':'TESTOFFLINE2026A2','attempt':1}
            json_request(base,'submit',badattempt,st,expected=409)
            sid=accepted['submission_id']
            json_request(base,'grade',{'submission_id':sid,'grades':[{'criterion_code':'RA4.a','instrument':'portafolio','score':8},{'criterion_code':'RA4.a','instrument':'prueba','score':6},{'criterion_code':'RA4.b','instrument':'portafolio','score':7},{'criterion_code':'RA4.b','instrument':'prueba','score':9}]},t)
            report=json_request(base,'report',None,t,{'group_id':group})
            result=report['students'][0]['assignments'][0]
            ok(result['criteria']['RA4.a']['final']==7.2,'El cálculo 60/40 de RA4.a es incorrecto')
            ok(result['criteria']['RA4.b']['final']==7.8,'El cálculo 60/40 de RA4.b es incorrecto')
            ok(result['ra']['RA4']['score']==7.5,'El RA no promedia equitativamente sus CE')
            history=json_request(base,'grade_history',None,t,{'submission_id':sid})['items']
            ok(len(history)==4,'Historial inicial de notas incompleto')
            json_request(base,'grade',{'submission_id':sid,'grades':[{'criterion_code':'RA4.a','instrument':'portafolio','score':9}]},t)
            history=json_request(base,'grade_history',None,t,{'submission_id':sid})['items']
            ok(len(history)==5 and history[0]['previous_score']==8 and history[0]['new_score']==9,'Auditoría de rectificaciones incorrecta')
            json_request(base,'grading_policy',{'module_code':'0441','weights':{'portafolio':1,'prueba':0}},t)
            report2=json_request(base,'report',None,t,{'group_id':group})
            ok(report2['students'][0]['assignments'][0]['criteria']['RA4.a']['final']==9,'Política por módulo no aplicada')
            ok(report2['students'][0]['assignments'][0]['criteria']['RA4.b']['final']==7,'CE no ponderado correctamente')
            json_request(base,'grading_policy',{'module_code':'0441','weights':{'portafolio':0.6,'prueba':0.4}},t)
            json_request(base,'grading_policy',{'module_code':'0441','weights':{'portafolio':0.8,'prueba':0.4}},t,expected=422)
            json_request(base,'grade',{'submission_id':sid,'grades':[{'criterion_code':'RA99.z','instrument':'prueba','score':9}]},t,expected=422)
            json_request(base,'grade_history',None,other_token,{'submission_id':sid},expected=403)
            # La carga de catálogo usa códigos proporcionados por la fuente oficial,
            # no inventa RA ni CE. Si hay catálogo, se rechazan criterios ajenos.
            json_request(base,'curricula',{'module_code':'0441','territory':'Canarias','version':'prueba-esquema','source_url':'https://www.boe.es/buscar/act.php?id=BOE-A-2009-19148','criteria':['RA4.a','RA4.b']},admin)
            json_request(base,'library',{'title':'Otro','external_id':'TEST-INVALID','module_code':'0441','criteria':[{'code':'RA9.z','ra':'RA9'}],'zip_base64':makezip('TEST-INVALID')},t,expected=422)
            with sqlite3.connect(db_path) as connection:
                connection.execute("UPDATE teacher_licenses SET expires_at=? WHERE source_ref='fixture-payment-1'",(int(time.time())-1,))
                connection.execute(
                    "INSERT INTO users(school_id,email,display_name,role,passhash) VALUES(?,?,'Segundo alumno','student','not-used')",
                    (school_id,'student2@example.test'))
            expired=json_request(base,'license',token=t)['license']
            ok(expired['licenses'][0]['state']=='expired' and expired['available_classrooms']==0,
               'La licencia no refleja la caducidad')
            json_request(base,'groups',{'name':'4º GA','academic_year':'2026-2027'},t,expected=403)
            json_request(base,'enroll',{'group_id':group,'student_email':'student@example.test'},t)
            json_request(base,'enroll',{'group_id':group,'student_email':'student2@example.test'},t,expected=403)
            json_request(base,'assign',{'group_id':group,'exercise_id':unassigned_exercise,'max_attempts':3},t,expected=403)
            json_request(base,'pull',None,st)
            ok(json_request(base,'pull',None,st)['items']==[],
               'El alumno recibe asignaciones de un aula con licencia caducada')
            json_request(base,'package',None,st,{'id':exercise},expected=403)
            json_request(base,'submit',delivery,st)
            json_request(base,'submit',{**delivery,'attempt':2,'event_id':'TESTOFFLINE2026A2'},st,expected=403)
            json_request(base,'enroll',{'group_id':legacy_group,'student_email':student},t)
            # Restablecimiento administrativo revoca sesiones y obliga a nuevo cambio.
            json_request(base,'reset_password',{'user_id':next(x['id'] for x in json_request(base,'users',None,admin)['items'] if x['email']==teacher),'new_password':'AnotherTempPass1234!'},admin)
            # Multicentro: alta reservada al titular, separación entre grupos y datos.
            schools=json_request(base,'schools',None,admin)
            ok(schools['can_create'] is True and len(schools['items'])==1,'No se reconoce al propietario del servidor')
            school=json_request(base,'schools',{'name':'IES Isla de Prueba','admin_name':'Admin segundo centro','admin_email':'admin2@example.test','admin_password':'StrongSchoolPass1234!'},admin,expected=201)
            new_adm=json_request(base,'login',{'email':'admin2@example.test','password':'StrongSchoolPass1234!'})['token']
            json_request(base,'groups',None,new_adm,expected=403)
            json_request(base,'change_password',{'current_password':'StrongSchoolPass1234!','new_password':'NewSchoolPass5678!'},new_adm)
            new_adm=json_request(base,'login',{'email':'admin2@example.test','password':'NewSchoolPass5678!'})['token']
            own=json_request(base,'groups',None,new_adm)
            ok(own['items']==[],'Datos de grupo filtrados entre centros')
            json_request(base,'report',None,new_adm,{'group_id':group},expected=403)
            json_request(base,'schools',{'name':'Centro ilegítimo','admin_name':'User','admin_email':'x@example.test','admin_password':'VeryStrong12345!'},new_adm,expected=403)
            json_request(base,'logout',{},st)
            json_request(base,'pull',None,st,expected=401)
            # Limitación de acceso por contraseña para un correo inexistente.
            for n in range(8):json_request(base,'login',{'email':'nadie@example.test','password':'badpassword'},expected=401)
            json_request(base,'login',{'email':'nadie@example.test','password':'badpassword'},expected=429)
            print('OK ('+layout+'): instalación, cuentas, roles, grupo, biblioteca, ZIP, asignación, descarga, entrega tardía, idempotencia, corrección RA/CE 60/40, permisos y rate-limit')
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill()

def php_config(dst,secret):
    def sq(v):return "'"+str(v).replace('\\','\\\\').replace("'","\\'")+"'"
    fields={'platform_owner_email':'admin@example.test','install_secret':secret,'base_url':'https://example.test/central','db_path':str(dst/'private'/'conta.sqlite3'),'upload_dir':str(dst/'private'/'packages'),'token_hours':8,'max_package_bytes':25*1024*1024,'max_submission_bytes':3*1024*1024}
    return '['+','.join(sq(k)+'=>'+str(v) if isinstance(v,int) else sq(k)+'=>'+sq(v) for k,v in fields.items())+']'

if __name__=='__main__':test_http()
