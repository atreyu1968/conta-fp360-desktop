"""Comprobar empaquetado de manifiestos de actualización sin necesitar claves privadas.
Prueba rutas Studio/Aula, arquitecturas, firmas y rechazo de artefactos incompletos.
No sustituye la firma real de GitHub Releases ni la instalación nativa.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TAG='v2.3.0'
NAMES={
    'windows-x86_64':'CONTA-FP360-{edition}_2.3.0_x64-setup.exe',
    'linux-x86_64':'CONTA-FP360-{edition}_2.3.0_amd64.AppImage',
    'darwin-aarch64':'CONTA-FP360-{edition}-darwin-aarch64.app.tar.gz',
    'darwin-x86_64':'CONTA-FP360-{edition}-darwin-x86_64.app.tar.gz'
}
def call(root,success=True):
    p=subprocess.run([sys.executable,str(ROOT/'scripts'/'create_manifest.py'),str(root),TAG],
                     capture_output=True,text=True)
    if success:
        assert p.returncode==0,(p.stdout,p.stderr)
    else:
        assert p.returncode!=0,(p.stdout,p.stderr)
    return p

with tempfile.TemporaryDirectory(prefix='conta_manifest_') as directory:
    base=Path(directory)
    for edition in ('Studio','Aula'):
        folder=base/edition
        folder.mkdir()
        for machine,template in NAMES.items():
            name=template.format(edition=edition)
            f=folder/name
            f.write_bytes(b'EXE or ZIP placeholder, NO SIGNATURE AUTHENTICITY')
            Path(str(f)+'.sig').write_text('TEST-SIGNATURE-'+edition+'-'+machine)
    call(base)
    for edition in ('Studio','Aula'):
        manifest=json.loads((base/(edition.lower()+'-latest.json')).read_text())
        assert manifest['version']=='2.3.0'
        assert set(manifest['platforms'])==set(NAMES)
        for machine,meta in manifest['platforms'].items():
            assert meta['url'].startswith('https://github.com/atreyu1968/conta-fp360-desktop/releases/download/'+TAG+'/')
            assert meta['signature']=='TEST-SIGNATURE-'+edition+'-'+machine
    # Se impide publicar si falta una firma Tauri de cualquier arquitectura.
    (base/'Aula'/('CONTA-FP360-Aula-darwin-aarch64.app.tar.gz.sig')).unlink()
    call(base,success=False)
    print('OK: manifiestos independientes, Windows/Linux/macOS x2 y firmas obligatorias')
