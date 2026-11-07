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

def makezip(external_id, unsafe=False):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.json', json.dumps({'schemaId': 'contafp360.alumno.v1', 'id': external_id, 'documentos': []}))
        if unsafe: z.writestr('soluciones/instructor.txt', 'NO DEBERIA EXISTIR')
    return base64.b64encode(stream.getvalue()).decode()

def test_http():
    assert SOURCE.joinpath('api.php').exists()
    with tempfile.TemporaryDirectory(prefix='cfp360-http-') as temp:
        dst = Path(temp) / 'www'
        shutil.copytree(SOURCE, dst)
        secret = 'secret-de-prueba-no-se-usa-en-produccion-0001'
        config = "<?php return " + php_config(dst, secret) + ";\n"
        (dst/'config.php').write_text(config)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        base=f'http://127.0.0.1:{port}'
        proc=subprocess.Popen(['php','-S',f'127.0.0.1:{port}','-t',str(dst)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            for attempt in range(80):
                try:
                    json_request(base,'health');break
                except Exception:
                    time.sleep(.1)
            else:raise AssertionError('No arranca PHP servidor')
            admin_email='admin@example.test'
            form = urllib.parse.urlencode({'secret':secret,'school':'IES Centro de Pruebas','name':'Administración del centro','email':admin_email,'password':'AdminTestPass12345'}).encode()
            with urllib.request.urlopen(urllib.request.Request(base+'/install.php',data=form),timeout=12) as r:
                body=r.read().decode()
                ok('Servidor instalado' in body,'No se ha completado la instalación')
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
            group=json_request(base,'groups',{'name':'2º GA','academic_year':'2026-2027'},t,expected=201)['group_id']
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
            assignment={'group_id':group,'exercise_id':exercise,'max_attempts':3,'due_at':'2020-01-01T00:00:00Z'}
            aid=json_request(base,'assign',assignment,t,expected=201)['assignment_id']
            redelivery=json_request(base,'assign',assignment,t)
            ok(redelivery['already_received'] and redelivery['assignment_id']==aid,'Asignación no idempotente')
            json_request(base,'report',None,st,{'group_id':group},expected=403)
            json_request(base,'report',None,other_token,{'group_id':group},expected=403)
            pulled=json_request(base,'pull',None,st)['items']
            ok(len(pulled)==1 and pulled[0]['assignment_id']==aid,'No llega la asignación al alumno')
            pkg=json_request(base,'package',None,st,{'id':exercise});ok(len(pkg)>30,'Paquete corrupto')
            delivery={'assignment_id':aid,'attempt':1,'event_id':'TESTOFFLINE2026A1','work':{'manifest_id':identifier,'asientos':[{'id':'1','debe':500,'haber':500}]}}
            accepted=json_request(base,'submit',delivery,st,expected=201)
            ok(accepted['late'] is True,'No se ha marcado como tardía una entrega offline recibida fuera del plazo')
            repeated=json_request(base,'submit',delivery,st)
            ok(repeated['already_received'] is True and repeated['submission_id']==accepted['submission_id'],'Reintento no idempotente')
            bad={**delivery,'work':{'asientos':[{'id':1,'debe':999}]}}
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
            # Restablecimiento administrativo revoca sesiones y obliga a nuevo cambio.
            json_request(base,'reset_password',{'user_id':next(x['id'] for x in json_request(base,'users',None,admin)['items'] if x['email']==teacher),'new_password':'AnotherTempPass1234!'},admin)
            json_request(base,'logout',{},st)
            json_request(base,'pull',None,st,expected=401)
            # Limitación de acceso por contraseña para un correo inexistente.
            for n in range(8):json_request(base,'login',{'email':'nadie@example.test','password':'badpassword'},expected=401)
            json_request(base,'login',{'email':'nadie@example.test','password':'badpassword'},expected=429)
            print('OK: instalación, cuentas, roles, grupo, biblioteca, ZIP, asignación, descarga, entrega tardía, idempotencia, corrección RA/CE 60/40, permisos y rate-limit')
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill()

def php_config(dst,secret):
    def sq(v):return "'"+str(v).replace('\\','\\\\').replace("'","\\'")+"'"
    fields={'install_secret':secret,'base_url':'https://example.test/central','db_path':str(dst/'private'/'conta.sqlite3'),'upload_dir':str(dst/'private'/'packages'),'token_hours':8,'max_package_bytes':25*1024*1024,'max_submission_bytes':3*1024*1024}
    return '['+','.join(sq(k)+'=>'+str(v) if isinstance(v,int) else sq(k)+'=>'+sq(v) for k,v in fields.items())+']'

if __name__=='__main__':test_http()
