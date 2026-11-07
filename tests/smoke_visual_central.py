"""Prueba de interfaz Central rediseñada con Chromium y API simulada.
Cubre contraseña temporal, menú docente, matriz RA/CE, política, historial,
administración y navegación de alumno. No sustituye las pruebas HTTP reales.
"""
import json
import shutil
import tempfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit,parse_qs
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]/'central'/'cpanel'

class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

with tempfile.TemporaryDirectory(prefix='central_ui_') as tmp:
    root=Path(tmp)
    html=(ROOT/'index.php').read_text().split('?>',1)[1]
    (root/'index.html').write_text(html)
    shutil.copytree(ROOT/'assets',root/'assets')
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(root)))
    Thread(target=server.serve_forever,daemon=True).start()
    try:
      with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
        for role in ('admin','student'):
            state={'temporary':role=='admin','requests':[],'role':role}
            context=browser.new_context(viewport={'width':1366,'height':900})
            page=context.new_page()
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            def route_api(route):
                url=urlsplit(route.request.url)
                action=parse_qs(url.query).get('r',['health'])[0]
                body=None
                if route.request.method=='POST':
                    body=json.loads(route.request.post_data or '{}')
                state['requests'].append((action,body))
                if action=='login':
                    result={'ok':True,'token':'Z'*64,'user':{'id':12 if role=='admin' else 15,
                        'school_id':1,'name':'Docente de prueba' if role=='admin' else 'Alumno de prueba',
                        'role':role,'must_change_password':state['temporary']}}
                elif action=='change_password':
                    state['temporary']=False
                    result={'ok':True,'relogin_required':True}
                elif action=='groups':
                    result={'ok':True,'items':[{'id':3,'name':'2º Gestión Administrativa A','academic_year':'2026-2027'}]}
                elif action=='library':
                    result={'ok':True,'items':[{'id':8,'external_id':'TEST-1','revision':1,'title':'Operaciones IGIC',
                        'module_code':'0441','criteria':[{'code':'RA4.a','ra':'RA4'}]}]}
                elif action=='pull':
                    result={'ok':True,'items':[{'assignment_id':5,'exercise_id':8,'title':'Operaciones IGIC',
                        'module_code':'0441','group_name':'2º Gestión Administrativa A','max_attempts':3}]}
                elif action=='report':
                    result={'ok':True,'students':[{'name':'Alumno de prueba','assignments':[{
                        'assignment_id':5,'title':'Operaciones IGIC',
                        'submission':{'id':9},'criteria':{'RA4.a':{'final':7.25},'RA4.b':{'final':None}},
                        'ra':{'RA4':{'score':None}}}]}]}
                elif action=='submissions':
                    result={'ok':True,'items':[{'id':9,'display_name':'Alumno de prueba','title':'Operaciones IGIC','attempt':1,
                        'criteria':[{'code':'RA4.a','ra':'RA4'},{'code':'RA4.b','ra':'RA4'}]}]}
                elif action=='users':
                    result={'ok':True,'items':[{'id':15,'display_name':'Alumno de prueba','email':'a@example.test','role':'student'}]}
                elif action=='grade_history':
                    result={'ok':True,'items':[{'id':1,'created_at':'2026-11-07','criterion_code':'RA4.a','instrument':'portafolio',
                        'previous_score':None,'new_score':7.25,'teacher_name':'Docente de prueba'}]}
                else:result={'ok':True}
                route.fulfill(status=200,json=result)
            page.route('**/api.php?*',route_api)
            page.goto('http://127.0.0.1:'+str(server.server_port)+'/index.html',wait_until='load')
            assert page.locator('#loginForm').is_visible()
            if role=='admin':
                page.locator('input[name=email]').fill('admin@example.test')
                page.locator('#loginForm input[name=password]').fill('temporary-pass')
                page.locator('#loginForm button').click()
                page.locator('#changePasswordForm').wait_for(state='visible')
                assert page.locator('#app').is_hidden(),'El panel se abrió antes de cambiar la clave temporal'
                page.locator('#changePasswordForm input[name=current_password]').fill('temporary-pass')
                page.locator('#changePasswordForm input[name=new_password]').fill('permanent-pass-1234')
                page.locator('#changePasswordForm button').click()
                page.wait_for_function("!window.location.href.includes('#') && document.querySelector('#loginForm')?.offsetParent!==null")
            page.locator('#loginForm input[name=email]').fill(role+'@example.test')
            page.locator('#loginForm input[name=password]').fill('permanent-pass-1234')
            page.locator('#loginForm button').click()
            page.locator('.workspace').wait_for(state='visible')
            if role=='admin':
                page.locator('button.side-link[data-view=assessment]').click()
                page.locator('details:has(#gradingPolicyForm) summary').click()
                page.locator('#gradingPolicyForm').wait_for(state='visible')
                page.locator('#gradingPolicyForm input[name=module_code]').fill('0441')
                page.locator('#gradingPolicyForm input[name=portafolio]').fill('70')
                page.locator('#gradingPolicyForm input[name=prueba]').fill('30')
                page.locator('#gradingPolicyForm button').click()
                page.wait_for_function("document.querySelector('#message')?.textContent.includes('Ponderación')")
                assert any(a=='grading_policy' and b and b['module_code']=='0441' for a,b in state['requests'])
                page.locator('details:has(#gradeHistory) summary').click()
                page.locator('#refreshGradeHistory').click()
                page.wait_for_function("document.querySelector('#gradeHistory')?.textContent.includes('RA4.a')")
                page.locator('button.side-link[data-view=admin]').click()
                assert page.locator('#curriculumForm').is_visible()
                assert page.locator('#resetPasswordForm').is_visible()
                page.locator('#top-change-password').click()
                page.locator('#changePasswordForm').wait_for(state='visible')
            else:
                assert page.locator('#studentAssignments').is_visible()
                assert page.locator('#studentAssignments').inner_text().find('Operaciones IGIC')>=0
                assert page.locator('button.side-link[data-view=admin]').count()==0
            assert not errors,errors
            print('OK Central Chromium:',role,'gestión de sesión, navegación y formularios')
            context.close()
        browser.close()
    finally:
        server.shutdown();server.server_close()
