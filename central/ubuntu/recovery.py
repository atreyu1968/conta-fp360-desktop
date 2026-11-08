#!/usr/bin/env python3
"""Copias verificables y restauración aislada de una instalación Ubuntu de Central."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import termios

FORMAT_VERSION = 1
DEFAULT_CONFIG = Path("/etc/conta-fp360/config.php")
DEFAULT_DATA = Path("/var/lib/conta-fp360")
MAX_MANIFEST_BYTES = 4 * 1024 * 1024


def set_admin_password(database: Path, email: str, password: str) -> subprocess.CompletedProcess[str]:
    """Replace one active admin's password without putting it in process arguments."""
    code = r'''
$database=$argv[1]; $email=$argv[2]; $password=stream_get_contents(STDIN);
if(strlen($password)<12 || strlen($password)>500) {
    fwrite(STDERR,"La contraseña debe contener entre 12 y 500 caracteres.\n"); exit(2);
}
try {
    $db=new PDO("sqlite:".$database,null,null,[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
    $db->exec("PRAGMA foreign_keys=ON; PRAGMA busy_timeout=5000");
    if($db->query("PRAGMA integrity_check")->fetchColumn()!=="ok") {
        throw new RuntimeException("SQLite no superó la comprobación de integridad.");
    }
    $db->exec("BEGIN IMMEDIATE");
    try {
        $find=$db->prepare("SELECT id,passhash FROM users WHERE email=? COLLATE NOCASE AND role='admin' AND active=1");
        $find->execute([$email]); $admin=$find->fetch(PDO::FETCH_ASSOC);
        if(!$admin) throw new RuntimeException("No se encontró una cuenta administradora activa con ese correo.");
        if(password_verify($password,$admin["passhash"])) {
            throw new RuntimeException("La nueva contraseña debe ser distinta de la actual.");
        }
        $update=$db->prepare("UPDATE users SET passhash=? WHERE id=? AND role='admin' AND active=1");
        $update->execute([password_hash($password,PASSWORD_DEFAULT),$admin["id"]]);
        if($update->rowCount()!==1) throw new RuntimeException("No se pudo actualizar la cuenta administradora.");
        $db->prepare("DELETE FROM tokens WHERE user_id=?")->execute([$admin["id"]]);
        $db->commit();
    } catch(Throwable $error) {
        if($db->inTransaction()) $db->rollBack();
        throw $error;
    }
    echo "Contraseña actualizada; se revocaron las sesiones de esa cuenta.\n";
} catch(Throwable $error) {
    fwrite(STDERR,$error->getMessage()."\n"); exit(1);
} finally {
    unset($password);
}
'''
    return subprocess.run(
        ["php", "-r", code, str(database), email],
        input=password, check=False, capture_output=True, text=True, timeout=30,
    )


def read_hidden_password(prompt: str) -> str:
    descriptor = None
    original = None
    try:
        descriptor = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
        if not os.isatty(descriptor):
            fail("No hay una terminal disponible para ocultar la contraseña.")
        original = termios.tcgetattr(descriptor)
        hidden = original.copy()
        hidden[3] &= ~termios.ECHO
        termios.tcsetattr(descriptor, termios.TCSAFLUSH, hidden)
        value = bytearray()
        os.write(descriptor, prompt.encode("utf-8"))
        while True:
            character = os.read(descriptor, 1)
            if not character or character in (b"\n", b"\r"):
                break
            value.extend(character)
        try:
            return bytes(value).decode("utf-8")
        except UnicodeDecodeError:
            fail("La contraseña debe poder representarse como texto UTF-8.")
    except (OSError, termios.error) as error:
        raise RuntimeError(
            f"No se pudo leer la contraseña de forma oculta en la terminal ({error})."
        ) from error
    finally:
        if descriptor is not None:
            try:
                if original is not None:
                    termios.tcsetattr(descriptor, termios.TCSAFLUSH, original)
                    os.write(descriptor, b"\n")
            finally:
                os.close(descriptor)


def reset_admin_password(args: argparse.Namespace) -> None:
    config = absolute(args.config, "La configuración")
    if config.is_symlink() or not config.is_file():
        fail("No se encuentra la configuración privada indicada.")
    values = php_config(config)
    database = absolute(Path(values["db_path"]), "La ruta SQLite")
    if database.is_symlink() or not database.is_file():
        fail("No se encuentra el archivo SQLite configurado.")
    email = args.email.strip()
    if not email or len(email) > 240 or "@" not in email:
        fail("Indique el correo de la cuenta administradora.")
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        fail("El cambio requiere una terminal interactiva para ocultar y confirmar la contraseña.")

    password = read_hidden_password("Nueva contraseña del administrador (12–500 caracteres): ")
    confirmation = read_hidden_password("Repita la contraseña: ")
    if password != confirmation:
        fail("Las contraseñas no coinciden.")
    if not 12 <= len(password) <= 500:
        fail("La contraseña debe contener entre 12 y 500 caracteres.")
    result = set_admin_password(database, email, password)
    del password, confirmation
    if result.returncode:
        message = result.stderr.strip()
        fail(message or "No se pudo actualizar la contraseña; SQLite no se modificó.")
    print(result.stdout, end="")


def fail(message: str) -> None:
    raise RuntimeError(message)


def absolute(path: Path, label: str) -> Path:
    if not path.is_absolute():
        fail(f"{label} debe ser una ruta absoluta.")
    if path.resolve(strict=False) != path:
        fail(f"{label} no puede pasar por enlaces simbólicos.")
    return path


def php_config(config: Path) -> dict[str, str]:
    code = (
        '$c=require $argv[1];'
        'if(!is_array($c)) throw new RuntimeException("configuración inválida");'
        'echo json_encode(["db_path"=>$c["db_path"]??null,'
        '"upload_dir"=>$c["upload_dir"]??null],JSON_THROW_ON_ERROR);'
    )
    result = subprocess.run(
        ["php", "-r", code, str(config)],
        check=False, capture_output=True, text=True, timeout=15,
    )
    if result.returncode:
        fail("PHP no pudo leer la configuración privada de Central.")
    try:
        values = json.loads(result.stdout)
    except json.JSONDecodeError:
        fail("La configuración privada no devolvió las rutas de Central.")
    if not isinstance(values, dict) or not all(
        isinstance(values.get(key), str) and Path(values[key]).is_absolute()
        for key in ("db_path", "upload_dir")
    ):
        fail("La configuración debe contener rutas absolutas para SQLite y paquetes.")
    return values


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check_tree_no_links(root: Path) -> list[Path]:
    files: list[Path] = []
    for current, directories, names in os.walk(root, followlinks=False):
        here = Path(current)
        for name in directories:
            path = here / name
            if path.is_symlink():
                fail(f"No se admiten enlaces simbólicos en datos privados: {path}")
        for name in names:
            path = here / name
            if path.is_symlink() or not path.is_file():
                fail(f"Solo se admiten archivos regulares en datos privados: {path}")
            files.append(path)
    return files


def check_database(database: Path) -> None:
    try:
        connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=10)
        try:
            result = connection.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                fail("SQLite no superó PRAGMA integrity_check; no se creó la copia.")
            tables = {
                row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if "central_paypal_settings" in tables:
                row = connection.execute(
                    "SELECT encrypted_payload FROM central_paypal_settings WHERE id=1"
                ).fetchone()
                if row and row[0] and not (database.parent / ".paypal-config.key").is_file():
                    fail("Hay credenciales PayPal cifradas, pero falta .paypal-config.key.")
        finally:
            connection.close()
    except sqlite3.Error:
        fail("No se pudo verificar SQLite. Compruebe que la base esté disponible.")


def verify_paypal_encryption(database: Path, key: Path) -> None:
    code = (
        '$db=new PDO("sqlite:".$argv[1]);'
        '$table=$db->query("SELECT 1 FROM sqlite_master WHERE type=\\"table\\" '
        'AND name=\\"central_paypal_settings\\"")->fetchColumn();'
        'if(!$table) exit(0);'
        '$payload=$db->query("SELECT encrypted_payload FROM central_paypal_settings '
        'WHERE id=1")->fetchColumn();if(!$payload) exit(0);'
        'if(!is_file($argv[2]) || filesize($argv[2])!==SODIUM_CRYPTO_SECRETBOX_KEYBYTES) exit(2);'
        '$bytes=base64_decode($payload,true);$n=SODIUM_CRYPTO_SECRETBOX_NONCEBYTES;'
        'if(!is_string($bytes)||strlen($bytes)<=$n) exit(3);'
        '$plain=sodium_crypto_secretbox_open(substr($bytes,$n),substr($bytes,0,$n),'
        'file_get_contents($argv[2]));'
        '$data=is_string($plain)?json_decode($plain,true):null;'
        'if(!is_array($data)||!is_string($data["client_id"]??null)||'
        '!is_string($data["client_secret"]??null)) exit(4);'
    )
    try:
        result = subprocess.run(
            ["php", "-r", code, str(database), str(key)],
            check=False, capture_output=True, text=True, timeout=15,
        )
    except subprocess.TimeoutExpired:
        fail("Se agotó el tiempo al verificar las credenciales PayPal restauradas.")
    if result.returncode:
        fail("La clave de la copia no descifra las credenciales PayPal de SQLite.")


def backup(args: argparse.Namespace) -> None:
    config = absolute(args.config, "La configuración")
    data = absolute(args.data_dir, "El directorio de datos")
    output = absolute(args.output, "La copia")
    if config.is_symlink() or not config.is_file():
        fail("No se encuentra la configuración privada indicada.")
    if data.is_symlink() or not data.is_dir():
        fail("No se encuentra el directorio privado de datos indicado.")
    if output.exists() or output.is_symlink():
        fail("La copia de destino ya existe; no se sobrescribirá.")
    if not output.parent.is_dir():
        fail("Cree primero la carpeta privada de copias.")
    if output.resolve(strict=False).is_relative_to(data.resolve()):
        fail("Guarde la copia fuera del directorio de datos que se está respaldando.")

    config_values = php_config(config)
    database = Path(config_values["db_path"])
    packages = Path(config_values["upload_dir"])
    if database.parent.resolve() != data.resolve() or packages.resolve() != (data / "packages").resolve():
        fail("SQLite y paquetes deben estar dentro del directorio de datos indicado.")
    if not database.is_file() or not packages.is_dir():
        fail("Falta SQLite o el directorio de paquetes.")
    absolute(database, "La ruta SQLite")
    absolute(packages, "La ruta de paquetes")
    check_database(database)

    key = data / ".paypal-config.key"
    if key.exists():
        if key.is_symlink() or not key.is_file() or key.stat().st_size != 32:
            fail("La clave .paypal-config.key no es un archivo regular válido de 32 bytes.")
    verify_paypal_encryption(database, key)

    with tempfile.TemporaryDirectory(prefix=".central-backup-", dir=output.parent) as temporary:
        stage = Path(temporary)
        (stage / "packages").mkdir(mode=0o700)
        shutil.copyfile(config, stage / "config.php")
        os.chmod(stage / "config.php", 0o600)
        # SQLite's backup API takes a consistent snapshot, including committed WAL data.
        source_db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=30)
        target_db = sqlite3.connect(stage / "central.sqlite3")
        try:
            source_db.backup(target_db)
            target_db.commit()
        finally:
            target_db.close()
            source_db.close()
        os.chmod(stage / "central.sqlite3", 0o600)
        for path in check_tree_no_links(packages):
            relative = path.relative_to(packages)
            destination = stage / "packages" / relative
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            shutil.copyfile(path, destination)
            os.chmod(destination, 0o600)
        if key.exists():
            shutil.copyfile(key, stage / ".paypal-config.key")
            os.chmod(stage / ".paypal-config.key", 0o600)
        verify_paypal_encryption(stage / "central.sqlite3", stage / ".paypal-config.key")

        paths = [p for p in stage.rglob("*") if p.is_file()]
        manifest = {
            "format": FORMAT_VERSION,
            "original_config": str(config),
            "original_data_dir": str(data),
            "files": {
                p.relative_to(stage).as_posix(): sha256(p)
                for p in sorted(paths)
            },
        }
        (stage / "manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        os.chmod(stage / "manifest.json", 0o600)
        try:
            with tarfile.open(output, "x:gz") as archive:
                for path in sorted(stage.rglob("*")):
                    relative = path.relative_to(stage).as_posix()
                    info = archive.gettarinfo(str(path), arcname=relative)
                    if path.is_file():
                        with path.open("rb") as stream:
                            archive.addfile(info, stream)
                    else:
                        archive.addfile(info)
            os.chmod(output, 0o600)
        except Exception:
            output.unlink(missing_ok=True)
            raise
    print(f"Copia creada y verificada: {output}")


def safe_archive(archive_path: Path, stage: Path) -> dict:
    try:
        archive = tarfile.open(archive_path, "r:gz")
    except (tarfile.TarError, OSError):
        fail("No se pudo abrir la copia comprimida.")
    with archive:
        members = archive.getmembers()
        names: set[str] = set()
        for member in members:
            relative = PurePosixPath(member.name)
            if (relative.is_absolute() or ".." in relative.parts or not relative.parts
                    or member.name in names or not (member.isfile() or member.isdir())):
                fail("La copia contiene rutas duplicadas o entradas no permitidas.")
            names.add(member.name)
            if member.isfile():
                destination = stage.joinpath(*relative.parts)
                destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    fail("La copia contiene un archivo ilegible.")
                with source, destination.open("xb") as target:
                    shutil.copyfileobj(source, target)
                os.chmod(destination, 0o600)
            else:
                stage.joinpath(*relative.parts).mkdir(mode=0o700, parents=True, exist_ok=True)
        manifest_path = stage / "manifest.json"
        if not manifest_path.is_file() or manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
            fail("La copia no incluye un manifiesto válido.")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            fail("El manifiesto de la copia está dañado.")
    if not isinstance(manifest, dict) or manifest.get("format") != FORMAT_VERSION:
        fail("Versión de copia no compatible.")
    try:
        original_data = Path(manifest["original_data_dir"])
        if not original_data.is_absolute():
            fail("El manifiesto no indica un directorio de datos absoluto.")
        config_values = php_config(stage / "config.php")
        if (Path(config_values["db_path"]).parent.resolve() != original_data.resolve()
                or Path(config_values["upload_dir"]).resolve()
                != (original_data / "packages").resolve()):
            fail("La configuración incluida no corresponde al directorio de datos respaldado.")
    except (KeyError, TypeError):
        fail("El manifiesto no indica el directorio de datos de origen.")
    expected = manifest.get("files")
    if not isinstance(expected, dict) or set(expected) != {
        p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file()
    } - {"manifest.json"}:
        fail("El contenido de la copia no coincide con su manifiesto.")
    for name, digest in expected.items():
        path = stage.joinpath(*PurePosixPath(name).parts)
        if not isinstance(digest, str) or len(digest) != 64 or sha256(path) != digest:
            fail(f"El archivo de la copia no supera la comprobación: {name}")
    required = {"config.php", "central.sqlite3"}
    if not required.issubset(expected) or not (stage / "packages").is_dir():
        fail("La copia no contiene configuración, SQLite y directorio de paquetes.")
    key_path = stage / ".paypal-config.key"
    if key_path.exists() and key_path.stat().st_size != 32:
        fail("La clave PayPal de la copia no tiene 32 bytes.")
    check_database(stage / "central.sqlite3")
    return manifest


def restore(args: argparse.Namespace) -> None:
    archive_path = absolute(args.archive, "La copia")
    target_config = absolute(args.config, "La configuración de destino")
    target_data = absolute(args.data_dir, "El directorio de datos de destino")
    if not archive_path.is_file() or archive_path.is_symlink():
        fail("No se encuentra el archivo de copia indicado.")
    if target_config.exists() or target_config.is_symlink():
        fail("La configuración de destino ya existe; no se sobrescribirá.")
    if not target_config.parent.is_dir():
        fail("Cree la carpeta padre de la configuración antes de restaurar.")
    if target_data.exists() or target_data.is_symlink():
        fail("El directorio de datos de destino ya existe; no se sobrescribirá.")
    resolved_config_parent = target_config.parent.resolve()
    resolved_data = target_data.resolve(strict=False)
    if (resolved_config_parent == resolved_data
            or resolved_config_parent.is_relative_to(resolved_data)
            or resolved_data.is_relative_to(resolved_config_parent)):
        fail("La configuración y los datos deben estar en directorios separados.")

    with tempfile.TemporaryDirectory(prefix="central-restore-") as temporary:
        stage = Path(temporary)
        manifest = safe_archive(archive_path, stage)
        verify_paypal_encryption(stage / "central.sqlite3", stage / ".paypal-config.key")
        target_data.mkdir(mode=0o700)
        try:
            packages = target_data / "packages"
            packages.mkdir(mode=0o700)
            shutil.copyfile(stage / "central.sqlite3", target_data / "conta-central.sqlite3")
            os.chmod(target_data / "conta-central.sqlite3", 0o600)
            for source in (stage / "packages").rglob("*"):
                if source.is_dir():
                    (packages / source.relative_to(stage / "packages")).mkdir(
                        mode=0o700, parents=True, exist_ok=True
                    )
                elif source.is_file():
                    destination = packages / source.relative_to(stage / "packages")
                    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    shutil.copyfile(source, destination)
                    os.chmod(destination, 0o600)
            key_source = stage / ".paypal-config.key"
            if key_source.exists():
                shutil.copyfile(key_source, target_data / ".paypal-config.key")
                os.chmod(target_data / ".paypal-config.key", 0o600)

            php_code = (
                '$c=require $argv[1];'
                '$c["db_path"]=$argv[2];$c["upload_dir"]=$argv[3];'
                'echo "<?php\\n// Configuración privada restaurada de Central.\\nreturn ".'
                'var_export($c,true).";\\n";'
            )
            rendered = subprocess.run(
                ["php", "-r", php_code, str(stage / "config.php"),
                 str(target_data / "conta-central.sqlite3"), str(packages)],
                check=False, capture_output=True, text=True, timeout=15,
            )
            if rendered.returncode:
                fail("PHP no pudo preparar la configuración restaurada.")
            descriptor = os.open(target_config, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(rendered.stdout)
                stream.flush()
                os.fsync(stream.fileno())
            if target_config.stat().st_size == 0:
                fail("La configuración restaurada está vacía.")
        except Exception:
            if target_config.exists():
                target_config.unlink()
            shutil.rmtree(target_data, ignore_errors=True)
            raise
    print("Restauración aislada completa; configuración, SQLite y paquetes no se sobrescribieron.")
    if (stage / ".paypal-config.key").exists() or ".paypal-config.key" in manifest["files"]:
        print("La clave privada de PayPal también se restauró.")
    else:
        print("La copia no contenía clave PayPal; no había una clave que restaurar.")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    backup_parser = commands.add_parser("backup", help="crear una copia consistente")
    backup_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    backup_parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    backup_parser.add_argument("--output", type=Path, required=True)
    restore_parser = commands.add_parser("restore", help="restaurar en destinos inexistentes")
    restore_parser.add_argument("--archive", type=Path, required=True)
    restore_parser.add_argument("--config", type=Path, required=True)
    restore_parser.add_argument("--data-dir", type=Path, required=True)
    password_parser = commands.add_parser(
        "reset-password", help="cambiar la contraseña de una cuenta administradora activa"
    )
    password_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    password_parser.add_argument("--email", required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "backup":
            backup(args)
        elif args.command == "restore":
            restore(args)
        else:
            reset_admin_password(args)
    except (RuntimeError, OSError, sqlite3.Error, subprocess.TimeoutExpired) as error:
        print(f"Error de recuperación: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
