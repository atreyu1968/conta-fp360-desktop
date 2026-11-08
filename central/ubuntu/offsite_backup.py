#!/usr/bin/env python3
"""Crea una copia cifrada de Central y la transfiere a un destino SSH."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

RECOVERY = Path(__file__).with_name("recovery.py")
TARGET_PATTERN = re.compile(r"^[A-Za-z0-9_.@-]+$")

REMOTE_CHECK = r"""
import pathlib, sys
p = pathlib.Path(sys.argv[1])
if p.is_symlink() or not p.is_dir():
    raise SystemExit("El directorio remoto no existe o no es un directorio normal.")
for name in sys.argv[2:]:
    if (p / name).exists() or (p / name).is_symlink():
        raise SystemExit("Ya existe una copia remota con ese nombre; no se sobrescribió.")
"""

REMOTE_VERIFY = r"""
import hashlib, pathlib, re, sys
p = pathlib.Path(sys.argv[1])
name = sys.argv[2]
archive, checksum = p / name, p / (name + ".sha256")
if p.is_symlink() or not p.is_dir() or archive.is_symlink() or checksum.is_symlink():
    raise SystemExit("No se pudo verificar la copia remota.")
if (not archive.is_file() or not checksum.is_file()
        or checksum.stat().st_size > 256):
    raise SystemExit("Falta la copia cifrada o su suma remota.")
line = checksum.read_text(encoding="ascii").strip()
if not re.fullmatch(r"[0-9a-f]{64}  " + re.escape(name), line):
    raise SystemExit("El archivo de suma remota tiene un formato inesperado.")
hasher = hashlib.sha256()
with archive.open("rb") as stream:
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        hasher.update(block)
digest = hasher.hexdigest()
if digest != line[:64]:
    raise SystemExit("La suma de la copia transferida no coincide.")
"""

REMOTE_RETENTION = r"""
from datetime import datetime, timedelta, timezone
import pathlib, re, sys
root = pathlib.Path(sys.argv[1])
days = int(sys.argv[2])
if root.is_symlink() or not root.is_dir() or days < 1:
    raise SystemExit("El directorio o la política de retención no son válidos.")
pattern = re.compile(r"^central-(\d{8}T\d{6}Z)\.tar\.gz\.age$")
cutoff = datetime.now(timezone.utc) - timedelta(days=days)
removed = 0
for archive in root.iterdir():
    match = pattern.fullmatch(archive.name)
    if not match or archive.is_symlink() or not archive.is_file():
        continue
    created = datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    if created < cutoff:
        archive.unlink()
        checksum = pathlib.Path(str(archive) + ".sha256")
        if checksum.is_file() and not checksum.is_symlink():
            checksum.unlink()
        removed += 1
print(f"Copias vencidas eliminadas: {removed}")
"""


def fail(message: str) -> None:
    raise RuntimeError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command: list[str], description: str) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command, check=False, capture_output=True, text=True, timeout=3600,
        )
    except FileNotFoundError:
        fail(f"No se encontró el programa necesario para {description}: {command[0]}.")
    except subprocess.TimeoutExpired:
        fail(f"Se agotó el tiempo durante {description}.")
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        fail(f"Falló {description}" + (f": {detail}" if detail else "."))
    return result


def remote_python(target: str, script: str, *arguments: str) -> str:
    remote_command = "python3 -c " + shlex.quote(script) + " " + " ".join(
        shlex.quote(argument) for argument in arguments
    )
    return run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
         "-o", "StrictHostKeyChecking=yes", "--", target, remote_command],
        "la comprobación remota",
    ).stdout


def create_archive(args: argparse.Namespace, destination: Path) -> None:
    command = [
        sys.executable, str(RECOVERY), "backup",
        "--config", str(args.config),
        "--data-dir", str(args.data_dir),
        "--output", str(destination),
    ]
    run(command, "crear la copia consistente")


def control_service(service: str, action: str) -> None:
    run(["systemctl", action, service], f"{action} el servicio {service}")


def encrypted_backup(args: argparse.Namespace) -> None:
    backup_dir = args.local_dir
    if not backup_dir.is_absolute() or backup_dir.is_symlink() or not backup_dir.is_dir():
        fail("El directorio local de trabajo debe existir y ser una ruta absoluta normal.")
    if backup_dir.resolve() != backup_dir:
        fail("El directorio local de trabajo no puede pasar por enlaces simbólicos.")
    os.chmod(backup_dir, 0o700)

    if not TARGET_PATTERN.fullmatch(args.ssh_target) or args.ssh_target.startswith("-"):
        fail("El destino SSH solo puede contener un usuario y un nombre de host válidos.")
    remote = PurePosixPath(args.remote_dir)
    if (not remote.is_absolute() or str(remote) != args.remote_dir
            or ".." in remote.parts or args.remote_dir == "/"):
        fail("El directorio remoto debe ser una ruta absoluta, normal y distinta de `/`.")
    if args.retention_days < 1 or args.retention_days > 3650:
        fail("La retención debe estar entre 1 y 3650 días.")
    if not args.recipient.startswith(("age1", "ssh-")):
        fail("Indique una clave pública de destinatario age (age1...) o SSH compatible.")
    for program in ("age", "rsync", "ssh"):
        if not shutil.which(program):
            fail(f"Instale `{program}` antes de ejecutar la copia externa.")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"central-{stamp}.tar.gz.age"
    checksum_name = filename + ".sha256"
    remote_dir = str(remote)
    remote_python(args.ssh_target, REMOTE_CHECK, remote_dir, filename, checksum_name)

    with tempfile.TemporaryDirectory(prefix=".central-offsite-", dir=backup_dir) as work:
        stage = Path(work)
        os.chmod(stage, 0o700)
        plain = stage / f"central-{stamp}.tar.gz"
        encrypted = stage / filename
        if args.no_service_control:
            create_archive(args, plain)
        else:
            try:
                control_service(args.service, "stop")
                create_archive(args, plain)
            finally:
                # Always try to bring the web service back, including on backup errors.
                control_service(args.service, "start")

        run(
            ["age", "--encrypt", "--recipient", args.recipient,
             "--output", str(encrypted), str(plain)],
            "cifrar la copia antes de transferirla",
        )
        if not encrypted.is_file() or encrypted.stat().st_size == 0:
            fail("age no produjo una copia cifrada válida.")
        digest = sha256(encrypted)
        checksum = stage / checksum_name
        checksum.write_text(f"{digest}  {filename}\n", encoding="ascii")
        os.chmod(encrypted, 0o600)
        os.chmod(checksum, 0o600)

        run(
            ["rsync", "--recursive", "--times", "--perms", "--partial",
             "--protect-args", "--ignore-existing",
             "--rsh=ssh -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=yes",
             str(encrypted), str(checksum), f"{args.ssh_target}:{remote_dir}/"],
            "transferir la copia cifrada",
        )
        remote_python(args.ssh_target, REMOTE_VERIFY, remote_dir, filename)
        retention_result = remote_python(
            args.ssh_target, REMOTE_RETENTION, remote_dir, str(args.retention_days)
        )
    print(f"Copia cifrada y transferida: {filename}")
    print(retention_result.strip())


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--config", type=Path, default=Path("/etc/conta-fp360/config.php"))
    root.add_argument("--data-dir", type=Path, default=Path("/var/lib/conta-fp360"))
    root.add_argument("--local-dir", type=Path, required=True,
                      help="directorio local privado para archivos temporales")
    root.add_argument("--recipient", required=True, help="clave pública age del centro")
    root.add_argument("--ssh-target", required=True, help="usuario y host del almacenamiento externo")
    root.add_argument("--remote-dir", required=True, help="directorio remoto ya creado")
    root.add_argument("--retention-days", type=int, default=35)
    root.add_argument("--service", default="apache2",
                      help="servicio que se detiene durante la instantánea (predeterminado: apache2)")
    root.add_argument("--no-service-control", action="store_true",
                      help=argparse.SUPPRESS)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        encrypted_backup(args)
    except (RuntimeError, OSError, ValueError) as error:
        print(f"Error en la copia externa: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
