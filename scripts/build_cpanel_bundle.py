#!/usr/bin/env python3
"""Empaqueta CONTA FP360 Central para el subdominio conta.redfp360.net.

No produce config.php ni contiene credenciales; la configuración privada
debe completarse directamente en el alojamiento cPanel.
"""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "central" / "cpanel"
DIST = ROOT / "dist"
NAME = "CONTA_FP360_Central_conta.redfp360.net"
DOMAIN = "https://conta.redfp360.net"

# Protección de errores: nunca incluir bases SQLite, configuración privada,
# directorios de carga, contraseñas, registros, respaldos ni cachés.
EXCLUDED_NAMES = {"config.php", ".env", "private", "packages", "backups",
                  "node_modules", "__pycache__", ".git", ".DS_Store"}
EXCLUDED_SUFFIXES = {".db", ".sqlite", ".sqlite3", ".db-wal", ".db-shm",
                     ".log", ".bak", ".key", ".pem"}
REQUIRED = {"index.php", "api.php", "bootstrap.php", "features.php",
            "config.example.php", "schema.sql", "install.php", ".htaccess",
            "assets/dashboard.js", "assets/visual.js"}
DOC = """CONTA FP360 CENTRAL · INSTALADOR 2.5 SIN CLAVE PARA CPANEL
Destino: https://conta.redfp360.net

RECOMENDACIÓN DE SEGURIDAD
Antes de subir los archivos, utilice «cPanel → Privacidad de directorios»
para proteger temporalmente la raíz del subdominio. Sin clave de instalación,
el primer visitante puede registrar una cuenta administradora. Si su panel
no permite privacidad de directorios, restrinja temporalmente el acceso por
IP o evite dejar el instalador accesible al público.

INSTALACIÓN
1. Compruebe PHP 8.2+, HTTPS y extensiones PDO_SQLITE, SQLite3 y ZIP.
2. Haga copia de seguridad del config.php anterior y de la base de datos.
3. Extraiga el ZIP de este paquete en la raíz de conta.redfp360.net,
   incluido .htaccess. No deje una carpeta intermedia llamada cpanel.
4. Abra https://conta.redfp360.net/install.php
5. El instalador muestra un diagnóstico de requisitos. Introduzca SOLO:
   - Nombre del centro educativo.
   - Nombre del administrador.
   - Correo electrónico del administrador.
   - Contraseña segura del administrador (mínimo 12 caracteres).
   NO se introduce clave de instalación; NO se edita config.php.
6. Pulse Instalar Central. El instalador creará config.php, la base SQLite
   y directorios privados en HOME/.conta-fp360, fuera de la web.
7. Si install.php permanece, elimínelo manualmente. Compruebe que no
   sea accesible. Quite la privacidad temporal del directorio, para
   permitir acceso normal a Central y a las aplicaciones.
8. Compruebe https://conta.redfp360.net/api.php?r=health:
   ok=true, initialized=true. Entre a https://conta.redfp360.net
   con su administrador.
9. En Studio y Aula use https://conta.redfp360.net como URL de Central.

NOTAS
- La contraseña de administrador NO es una clave de instalación.
- El archivo antiguo instalacion.clave, si existe, ya no se utiliza.
- Si hay base de datos previa, el asistente nunca la sobrescribe sin más.
- No active permisos 777. No utilice datos reales antes de verificar
  la protección de datos, los permisos y las copias de seguridad.
"""
def main():
    if not SRC.is_dir():
        raise SystemExit("No se encuentra central/cpanel")
    files={}
    for path in sorted(SRC.rglob("*")):
        if not path.is_file(): continue
        rel=path.relative_to(SRC)
        if any(part in EXCLUDED_NAMES or part.startswith(".env") for part in rel.parts):
            continue
        if path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        content=path.read_bytes()
        if rel.as_posix()=="config.example.php":
            content=content.replace(b"https://SU-DOMINIO.EJEMPLO/conta-fp360",
                                    DOMAIN.encode("utf-8"))
            if DOMAIN.encode("utf-8") not in content:
                raise SystemExit("La plantilla de configuración no acepta el dominio")
        files[rel.as_posix()]=content
    missing=REQUIRED - set(files)
    if missing:
        raise SystemExit("Faltan archivos críticos: "+", ".join(sorted(missing)))
    files["INSTALACION_CPANEL.txt"]=DOC.encode("utf-8")
    DIST.mkdir(parents=True,exist_ok=True)
    target=DIST/(NAME+".zip")
    with ZipFile(target,"w",ZIP_DEFLATED,compresslevel=9) as out:
        for name,content in sorted(files.items()):
            out.writestr(name,content)
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    (DIST/(NAME+"_SHA256.txt")).write_text(digest+"  "+target.name+"\n")
    with ZipFile(target) as check:
        assert check.testzip() is None
        assert "config.php" not in check.namelist()
        assert "INSTALACION_CPANEL.txt" in check.namelist()
    print(f"OK: {target.name} ({target.stat().st_size} bytes), SHA256 {digest}")
if __name__=="__main__":
    main()
