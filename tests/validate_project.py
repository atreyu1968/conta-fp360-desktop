"""Validación de integridad y aislamiento. No sustituye una compilación Windows."""
from pathlib import Path
from html.parser import HTMLParser
import json
ROOT=Path(__file__).resolve().parents[1]
base=json.loads((ROOT/'src-tauri/tauri.conf.json').read_text(encoding='utf-8'))
aula=json.loads((ROOT/'src-tauri/tauri.aula.conf.json').read_text(encoding='utf-8'))
assert base['identifier']!=aula['identifier']
assert base['build']['frontendDist']!=aula['build']['frontendDist']
assert base['bundle']['windows']['webviewInstallMode']['type']=='offlineInstaller'
assert base['app']['withGlobalTauri'] is True
assert base['app']['windows'][0]['useHttpsScheme'] is True
assert aula['app']['windows'][0]['useHttpsScheme'] is True
assert 'nsis' in base['bundle']['targets']
class Sources(HTMLParser):
 def __init__(self):
  super().__init__(); self.remote=[]
 def handle_starttag(self,tag,attrs):
  if tag in ('script','link'):
   d=dict(attrs); src=d.get('src','') or d.get('href','')
   if src.startswith(('http://','https://')) and (tag=='script' or d.get('rel')=='stylesheet'): self.remote.append(src)
for ed in ('studio','aula'):
 folder=ROOT/'web'/ed
 html=(folder/'index.html').read_text(encoding='utf-8')
 assert '<script src="./desktop-bridge.js"></script>' in html
 assert 'data-cfp-other' in html
 assert 'CONTA FP360' in html
 parser=Sources();parser.feed(html)
 assert not parser.remote,(ed,parser.remote)
 assert (folder/'desktop-bridge.js').is_file()
 print(ed,len(html),'caracteres, recursos internos OK')
assert (ROOT/'web/studio/desktop-bridge.js').read_bytes()==(ROOT/'web/aula/desktop-bridge.js').read_bytes()
assert 'save_export' in (ROOT/'src-tauri/src/lib.rs').read_text(encoding='utf-8')
assert 'CONTA_DESKTOP?.createPrintWindow?.()' in (ROOT/'web/aula/index.html').read_text(encoding='utf-8')
print('Estructura, aislamiento y recursos locales: OK')
