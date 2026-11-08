"""Prueba real en Chromium del arranque SQLite simulado y funciones existentes.
La compilación Tauri/Rust y el uso real del disco se verifican en los trabajos nativos.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright
import base64

ROOT = Path(__file__).resolve().parents[1]

INIT = r"""
(() => {
  window.__savedExports = [];
  window.__sqliteFake = {local: new Map(), objects: new Map()};
  window.localStorage.setItem('cfp360_migracion_demo','valor_legacy');
  window.__TAURI__ = {
    core: {
      invoke: async (cmd, args={}) => {
        const db = window.__sqliteFake[args.namespace];
        if(cmd==='sqlite_get') return db.get(args.key) ?? null;
        if(cmd==='sqlite_list') return [...db].map(([key,value])=>({key,value}));
        if(cmd==='sqlite_put_many') {
          for(const item of args.entries)db.set(item.key,item.value);
          return null;
        }
        if(cmd==='sqlite_put'){db.set(args.key,args.value);return null;}
        if(cmd==='sqlite_delete'){db.delete(args.key);return null;}
        if(cmd==='sqlite_backup')return true;
        if(cmd==='sqlite_restore')return false;
        if(cmd==='save_export') {window.__savedExports.push(args);return true;}
        throw Error('Comando nativo no simulado: '+cmd);
      }
    },
    opener:{openUrl:async()=>{}}
  };
})();
"""

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox','--disable-dev-shm-usage'])
    for ed in ('studio','aula'):
        server = ThreadingHTTPServer(
            ('127.0.0.1', 0),
            partial(QuietHandler, directory=str(ROOT/'web'/ed))
        )
        Thread(target=server.serve_forever, daemon=True).start()
        try:
            context = browser.new_context(viewport={'width':1366,'height':900})
            context.add_init_script(script=INIT)
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda err: errors.append(str(err)))
            page.on('dialog',lambda dialog:dialog.accept())
            page.goto(f'http://127.0.0.1:{server.server_port}/index.html',wait_until='load')
            page.evaluate('window.CONTA_DESKTOP.ready')
            page.wait_for_function("document.querySelector('main') !== null")
            assert page.locator('main').count()==1, (ed,'interfaz no cargada')
            assert page.locator('#cfp-sqlite-backup').count()==1, (ed,'falta copia SQLite')
            assert page.evaluate("window.__sqliteFake.local.get('cfp360_migracion_demo')")=='valor_legacy'
            assert page.evaluate("window.__sqliteFake.local.get('__migration_v1')")=='1'
            page.evaluate("localStorage.setItem('cfp360_prueba_sqlite','guardado')")
            page.evaluate("window.CONTA_DESKTOP.flush()")
            assert page.evaluate("window.__sqliteFake.local.get('cfp360_prueba_sqlite')")=='guardado'
            page.evaluate("localStorage.removeItem('cfp360_prueba_sqlite')")
            page.evaluate("window.CONTA_DESKTOP.flush()")
            assert page.evaluate("window.__sqliteFake.local.has('cfp360_prueba_sqlite')") is False
            pdf = page.evaluate("""async () => {
                const pack = {manifest:{id:'TEST',documentos:[]},
                  pdfs:{'documentos/test.pdf':new Uint8Array([37,80,68,70])}};
                await CONTA_DESKTOP.dbSet('package',pack);
                const got = await CONTA_DESKTOP.dbGet('package');
                return [...got.pdfs['documentos/test.pdf']];
            }""")
            assert pdf==[37,80,68,70],(ed,'fallo al recuperar PDF binario')
            page.evaluate("""() => {
                const blob=new Blob(['CONTA FP360'],{type:'application/json'});
                const a=document.createElement('a');
                a.download='prueba.json';a.href=URL.createObjectURL(blob);a.click();
            }""")
            page.wait_for_function('window.__savedExports.length===1', timeout=8000)
            saved = page.evaluate('window.__savedExports[0]')
            assert saved['filename']=='prueba.json'
            assert base64.b64decode(saved['base64Data'])==b'CONTA FP360'
            assert not errors,(ed, errors[:8])
            print(ed.upper(), 'arranque, migración, SQLite, PDF y exportación: OK')
            context.close()
        finally:
            server.shutdown()
            server.server_close()
    browser.close()
