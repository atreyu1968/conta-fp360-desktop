"""Genera manifiestos Tauri separados para Studio y Aula desde artefactos .sig."""
import sys,json
from pathlib import Path
from datetime import datetime,timezone
root=Path(sys.argv[1]);tag=sys.argv[2]
if not tag.startswith('v'):raise SystemExit('Tag vX.Y.Z requerido')
for edition in ('Studio','Aula'):
 folder=root/edition
 platforms={}
 rules={'windows-x86_64':'**/*-setup.exe','linux-x86_64':'**/*.AppImage',
        'darwin-aarch64':'**/*aarch64*.app.tar.gz','darwin-x86_64':'**/*x86_64*.app.tar.gz'}
 for machine,pattern in rules.items():
  files=list(folder.glob(pattern))
  if len(files)!=1:raise SystemExit(f'{edition}/{machine}: se esperaba un artefacto; encontrados {len(files)}')
  f=files[0];sig=Path(str(f)+'.sig')
  if not sig.exists():raise SystemExit('Sin firma: '+str(f))
  platforms[machine]={'url':f'https://github.com/atreyu1968/conta-fp360-desktop/releases/download/{tag}/{f.name}',
                      'signature':sig.read_text().strip()}
 out=root/(edition.lower()+'-latest.json')
 out.write_text(json.dumps({'version':tag[1:],'notes':f'Actualización oficial firmada CONTA FP360 {edition}',
          'pub_date':datetime.now(timezone.utc).isoformat(),'platforms':platforms},indent=2))
 print(out)
