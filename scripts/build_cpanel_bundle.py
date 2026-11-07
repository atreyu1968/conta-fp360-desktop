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
DOC = """CONTA FP360 CENTRAL · INSTALADOR AUTOMÁTICO 2.4 PARA CPANEL
Destino: https://conta.redfp360.net

ANTES DE EMPEZAR
- PHP 8.2 o superior, PDO_SQLITE, SQLite3, ZIP y HTTPS válidos.
- El directorio raíz del subdominio debe permitir escribir un archivo config.php.
- Copia de seguridad del alojamiento anterior antes de reemplazar el programa.

INSTALACIÓN (SIN EDITAR CONFIG.PHP)
1. Suba el ZIP de este paquete a la carpeta raíz del subdominio y extráigalo.
   Los archivos index.php, api.php, install.php y .htaccess deben quedar
   directamente en esa carpeta. Active Mostrar archivos ocultos en cPanel.
   Al reemplazar una instalación anterior, compruebe que .htaccess sea el
   incluido en este paquete. No suba datos reales ni contraseñas en el ZIP.
2. Abra https://conta.redfp360.net/install.php en un navegador por HTTPS.
3. El instalador crea una carpeta privada en la carpeta personal de cPanel
   llamada .conta-fp360 y un archivo instalacion.clave. Este archivo NO se
   publica por HTTP: se abre desde cPanel > Administrador de archivos >
   carpeta principal (HOME) > Mostrar ocultos > .conta-fp360.
4. Copie el código del archivo instalacion.clave en el formulario del
   instalador e introduzca centro, nombre de administrador, correo y clave.
   La autorización evita que otro visitante del nuevo sitio se registre
   como administrador antes que usted.
5. El instalador valida los requisitos, genera config.php automáticamente,
   repara una ruta SQLite anterior incorrecta (si no hay base de datos
   previa que proteger), crea SQLite y el usuario administrativo.
6. Si tras el éxito sigue presente install.php, bórrelo manualmente
   (el instalador intenta eliminarse por sí solo).
7. Abra https://conta.redfp360.net/api.php?r=health (ok e initialized=true)
   y acceda a https://conta.redfp360.net con el usuario creado.
8. En los botones Central de Studio y Aula, introduzca únicamente
   https://conta.redfp360.net e inicie sesión con cuentas individuales.

SEGURIDAD
- No es necesario editar config.example.php para una instalación nueva.
- La clave instalacion.clave es temporal, generada en el hosting y borrada
  al completar la instalación. No se imprime en el navegador ni se envía
  por correo. Nunca introduzca claves en incidencias ni en GitHub.
- Las bases y los paquetes están fuera de las carpetas públicas.
- No active permisos 777. No continúe con datos reales sin la comprobación
  RGPD/LOPDGDD y una copia de seguridad consistente de SQLite.
- Si la instalación informa de que HOME no es escribible, deberá revisar
  el propietario/permisos de la cuenta PHP con el proveedor.
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
