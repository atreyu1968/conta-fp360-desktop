"""Paquete reproducible de fuentes Central para Ubuntu, sin datos ni credenciales."""
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
import hashlib
import sys

ROOT=Path(__file__).resolve().parents[1]
DEST=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'generated-artifacts/CONTA-FP360-Central-Ubuntu-Server.zip'
PUBLIC={'api.php','bootstrap.php','features.php','paypal.php','index.php','install.php',
        'config.example.php','schema.sql','.htaccess','private/.htaccess'}
files=[]
for file in (ROOT/'central/cpanel').rglob('*'):
    if not file.is_file() or file.is_symlink():
        continue
    relative=file.relative_to(ROOT/'central/cpanel').as_posix()
    if relative in PUBLIC or (relative.startswith('assets/') and file.suffix in {'.css','.js','.png','.svg','.ico'}):
        files.append(file)
files += [file for file in (ROOT/'central/ubuntu').glob('*') if file.is_file() and file.suffix in {'.php','.conf','.sh','.py'}]
files += list((ROOT/'central/tests').glob('*.py'))
files += [ROOT/'central/README.md',ROOT/'UBUNTU_SERVER.md',ROOT/'IMPORTACION.md',ROOT/'VALIDACION.md',ROOT/'PAYPAL_CENTRAL.md']
DEST.parent.mkdir(parents=True,exist_ok=True)
with ZipFile(DEST,'w',ZIP_DEFLATED,compresslevel=9) as bundle:
    for file in sorted(files):
        # Fecha fija para poder comparar SHA-256 de paquetes del mismo código.
        info=ZipInfo(file.relative_to(ROOT).as_posix(),date_time=(2026,1,1,0,0,0))
        info.compress_type=ZIP_DEFLATED
        info.external_attr=0o100644 << 16
        bundle.writestr(info,file.read_bytes())
with ZipFile(DEST) as bundle:
    assert bundle.testzip() is None
    assert not any(Path(name).name=='config.php' or Path(name).suffix in {'.sqlite','.sqlite3','.db','.log','.bak'} for name in bundle.namelist())
checksum=hashlib.sha256(DEST.read_bytes()).hexdigest()
DEST.with_suffix('.zip.sha256').write_text(checksum+'  '+DEST.name+'\n')
print(f'Paquete de fuentes creado: {DEST.name} ({DEST.stat().st_size} bytes), sin configuración privada.')
