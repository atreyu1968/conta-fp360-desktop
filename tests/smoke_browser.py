"""Pruebas Chromium locales con puente simulado. No sustituyen WebView2 nativo."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import base64
ROOT=Path(__file__).resolve().parents[1]
BRIDGE=(ROOT/'web/studio/desktop-bridge.js').read_text(encoding='utf-8')
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
 for ed in ('studio','aula'):
  page=browser.new_page(viewport={'width':1366,'height':900})
  errors=[]
  page.on('pageerror',lambda err:errors.append(str(err)))
  page.on('dialog',lambda d:d.accept())
  page.set_content((ROOT/'web'/ed/'index.html').read_text(encoding='utf-8'),wait_until='load')
  page.wait_for_timeout(550)
  assert page.locator('main').count()==1,(ed,'no carga interfaz')
  assert not errors,(ed,errors[:5])
  page.evaluate("""() => {window.__savedExports=[];window.__TAURI__={
    core:{invoke:async (cmd,args)=>{if(cmd!=='save_export')throw Error(cmd);window.__savedExports.push(args);return true;}},
    opener:{openUrl:async()=>{}}};}""")
  page.add_script_tag(content=BRIDGE)
  assert page.evaluate('!!window.CONTA_DESKTOP')
  page.evaluate("""() => {const b=new Blob(['CONTA FP360'],{type:'application/json'});
    const a=document.createElement('a');a.download='prueba.json';a.href=URL.createObjectURL(b);a.click();}""")
  page.wait_for_function('window.__savedExports.length===1',timeout=5000)
  got=page.evaluate('window.__savedExports[0]')
  assert got['filename']=='prueba.json'
  assert base64.b64decode(got['base64Data'])==b'CONTA FP360'
  assert not errors,(ed,errors)
  print(ed.upper(),'interfaz y guardado simulado: OK')
  page.close()
 browser.close()
