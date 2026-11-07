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
DOC = """CONTA FP360 CENTRAL · INSTALACIÓN EN CPANEL
Destino público: https://conta.redfp360.net
Repositorio: atreyu1968/conta-fp360-desktop · rama de consolidación.

1. Crear conta.redfp360.net como dominio/subdominio con directorio propio.
   Comprobar que tiene registro DNS y HTTPS con certificado válido.
2. Seleccionar PHP 8.2 o superior. Habilitar PDO_SQLITE, sqlite3 y ZIP.
3. Subir ESTE ZIP al directorio raíz del subdominio y EXTRAERLO allí.
   IMPORTANTE: index.php y api.php deben quedar en la raíz del subdominio,
   no dentro de otra carpeta 'cpanel' o 'central'.
4. Copiar config.example.php como config.php. La URL del dominio
   ya está preconfigurada. Cambiar los marcadores 'REEMPLAZAR-...'
   por una clave de instalación aleatoria (>=32 caracteres) y el correo
   del administrador propietario. Nunca almacenar esas claves en GitHub.
5. Comprobar las rutas de db_path y upload_dir. Deben apuntar FUERA
   del directorio público de la web, con permisos de escritura PHP.
   Si el alojamiento no lo permite, no registrar alumnado real.
6. Abrir https://conta.redfp360.net/install.php y completar el centro
   y el primer administrador. Inmediatamente DESPUÉS, ELIMINAR install.php.
7. Comprobar https://conta.redfp360.net/api.php?r=health.
   Debe devolver ok=true e initialized=true. El campo initialized no
   sustituye la prueba de login ni garantiza que el DNS esté propagado.
8. Acceder a https://conta.redfp360.net/ y crear profesores,
   estudiantes y grupos. Introducir https://conta.redfp360.net en
   Studio y Aula > Central (SIN /api.php, /install.php ni /index.php).
9. Antes de trabajar con alumnado: validar currículo RA/CE, permisos
   de los centros, seguridad, copia consistente SQLite y RGPD/LOPDGDD.
   Las contraseñas de usuarios nuevas son temporales; cambiarlas al
   primer acceso.

No incluye credenciales ni datos personales. Solo es el paquete web.
Studio y Aula se instalan por separado; la firma del actualizador Tauri
y la firma/notarización comercial son procesos independientes.
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
