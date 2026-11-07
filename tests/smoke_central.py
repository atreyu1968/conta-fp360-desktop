"""Smoke real Chromium de Central en Studio/Aula, sin servidor ni datos reales."""
import hashlib
import io
import json
import zipfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit, parse_qs
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]

INIT=r"""
(()=> {
 window.__fake={local:new Map(),objects:new Map(),requests:[]};
 window.__TAURI__={core:{invoke:async(cmd,args={})=>{
  const db=window.__fake[args.namespace];
  if(cmd==='sqlite_get')return db.get(args.key)??null;
  if(cmd==='sqlite_list')return [...db].map(([key,value])=>({key,value}));
  if(cmd==='sqlite_put_many'){for(const x of args.entries)db.set(x.key,x.value);return null;}
  if(cmd==='sqlite_put'){db.set(args.key,args.value);return null;}
  if(cmd==='sqlite_delete'){db.delete(args.key);return null;}
  if(cmd==='sqlite_backup')return true;
  if(cmd==='sqlite_restore')return false;
  if(cmd==='cfp_check_update')return {enabled:false,available:false};
  if(cmd==='save_export')return true;
  throw Error('Comando inesperado '+cmd);
 }} ,opener:{openUrl:async()=>{}}};
})();
"""
def pack(eid):
    s=io.BytesIO()
    m={'schemaId':'contafp360.alumno.v1','id':eid,'documentos':[],
       'operaciones':[],'empresa':{'nombre':'Prueba sin conexión'},
       'curriculo':{'modulo':{'codigo':'0441'}}}
    with zipfile.ZipFile(s,'w',zipfile.ZIP_STORED) as f:
        f.writestr('manifest.json',json.dumps(m))
    return s.getvalue()

class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

def response(route,student):
    if route=='login':
        return {'ok':True,'token':'A'*64,'user':{'id':31 if student else 15,
          'name':'Alumno de pruebas' if student else 'Profesor de pruebas',
          'role':'student' if student else 'teacher','school_id':1}}
    if route=='pull':
        return {'ok':True,'items':[{'assignment_id':81,'title':'Supuesto de prueba','external_id':'TEST_SYNC',
          'exercise_id':11,'revision':1,'module_code':'0441','max_attempts':3,
          'sha256':hashlib.sha256(pack('TEST_SYNC')).hexdigest()}]}
    if route in ('library','groups'):
        return {'ok':True,'items':[]}
    if route in ('submit','assign','logout'):
        return {'ok':True}
    if route=='report':return {'ok':True,'students':[]}
    return {'ok':True,'items':[]}

with sync_playwright() as playwright:
    browser=playwright.chromium.launch(headless=True,args=['--no-sandbox'])
    for edition in ('studio','aula'):
        server=ThreadingHTTPServer(('127.0.0.1',0),
              partial(Quiet,directory=str(ROOT/'web'/edition)))
        Thread(target=server.serve_forever,daemon=True).start()
        try:
            base=f'http://127.0.0.1:{server.server_port}'
            context=browser.new_context(viewport={'width':1440,'height':920})
            context.add_init_script(script=INIT)
            page=context.new_page()
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            def handle(route):
                parsed=urlsplit(route.request.url)
                action=parse_qs(parsed.query).get('r',['health'])[0]
                if action=='package':
                    route.fulfill(status=200,body=pack('TEST_SYNC'),
                            headers={'Content-Type':'application/zip'})
                else:
                    route.fulfill(status=200,json=response(action,edition=='aula'))
            page.route('**/api.php?*',handle)
            page.goto(base+'/index.html',wait_until='load')
            page.evaluate('window.CONTA_DESKTOP.ready')
            page.evaluate('window.CONTA_CENTRAL.identityReady')
            page.locator('#cfp-central-button').click()
            page.locator('#central-server').fill(base)
            page.locator('#central-server').dispatch_event('change')
            page.locator('#central-email').fill('alumno@example.test' if edition=='aula' else 'profe@example.test')
            page.locator('#central-password').fill('test-password')
            page.locator('button[data-central="login"]').click()
            page.wait_for_function("Boolean(window.__fake.objects.get('central_identity'))")
            profile=json.loads(page.evaluate("window.__fake.objects.get('central_identity')"))
            assert profile['id']==(31 if edition=='aula' else 15)
            if edition=='aula':
                page.locator('button[data-central="receive"]').click()
                page.wait_for_function("Boolean(window.__fake.objects.get('central_profile_1_31_assignments'))")
                page.locator('button[data-central="download"]').click()
                page.wait_for_function("""()=>{
                  const raw=window.__fake.objects.get('package');
                  if(!raw)return false;
                  try{return JSON.parse(raw).manifest.id==='TEST_SYNC';}catch{return false;}
                }""",timeout=15000)
                page.wait_for_function("Boolean(window.__fake.objects.get('central_profile_1_31_active_assignment'))")
                page.evaluate("""()=>{
                  localStorage.setItem('cfp360_journal_TEST_SYNC',
                   JSON.stringify({asientos:[{id:'A1',lineas:[]}],cuentas:{}}));
                }""")
                page.locator('button[data-central="prepare"]').click()
                page.wait_for_function("Boolean(window.__fake.objects.get('central_profile_1_31_queue'))")
                queued=json.loads(page.evaluate("window.__fake.objects.get('central_profile_1_31_queue')"))
                assert len(queued)==1 and queued[0]['action']=='submit' and queued[0]['owner_id']==31,queued
                assert queued[0]['payload']['work']['manifest_id']=='TEST_SYNC'
                # Logout, no token; el trabajo continúa offline con el perfil del dispositivo.
                page.locator('button[data-central="logout"]').click()
                page.locator('button[data-central="prepare"]').click()
                page.wait_for_function("JSON.parse(window.__fake.objects.get('central_profile_1_31_queue')||'[]').length===2")
                queued=json.loads(page.evaluate("window.__fake.objects.get('central_profile_1_31_queue')"))
                assert [i['payload']['attempt'] for i in queued]==[1,2],queued
            else:
                project=page.evaluate("window.CONTA_FP360_STUDIO_STATE?.()")
                assert project and project.get('id')
                page.locator('#central-zip').set_input_files({
                    'name':'alumnado.zip','mimeType':'application/zip','buffer':pack(project['id'])
                })
                page.locator('button[data-central="publish"]').click()
                page.wait_for_function("Boolean(window.__fake.objects.get('central_profile_1_15_queue'))")
                queued=json.loads(page.evaluate("window.__fake.objects.get('central_profile_1_15_queue')"))
                assert len(queued)==1 and queued[0]['action']=='publish',queued
                assert queued[0]['payload']['external_id']==project['id']
            assert not errors,(edition,errors[:10])
            print('OK:',edition,'autenticación inicial, SQLite, biblioteca/entrega offline')
            context.close()
        finally:
            server.shutdown()
            server.server_close()
    browser.close()
