"""Unifica la configuración para compilar actualizaciones Tauri firmadas."""
import json,sys,os
from pathlib import Path
root=Path(__file__).resolve().parents[1]/'src-tauri'
base=json.loads((root/'tauri.conf.json').read_text())
def merge(a,b):
 for k,v in b.items():
  if isinstance(v,dict) and isinstance(a.get(k),dict):merge(a[k],v)
  else:a[k]=v
assert sys.argv[1] in ('Studio','Aula')
if sys.argv[1]=='Aula':merge(base,json.loads((root/'tauri.aula.conf.json').read_text()))
base['bundle']['createUpdaterArtifacts']=True
# Firma ad-hoc para pruebas Mac; no sustituye Developer ID ni notarización.
# Si APPLE_SIGNING_IDENTITY está configurada, Tauri usará esa identidad real.
if sys.platform == 'darwin' and not os.environ.get('APPLE_SIGNING_IDENTITY'):
    base['bundle'].setdefault('macOS', {})['signingIdentity'] = '-'
(root/'tauri.release.generated.conf.json').write_text(json.dumps(base,indent=2))
