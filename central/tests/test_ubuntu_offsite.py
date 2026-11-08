"""Prueba cifrado age, transferencia simulada y restauración desde el destino."""
from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
OFFSITE = ROOT / "central/ubuntu/offsite_backup.py"
SETUP = ROOT / "central/ubuntu/setup.php"


def run(*args, env=None):
    return subprocess.run(
        ["python3", str(OFFSITE), *map(str, args)],
        capture_output=True, text=True, timeout=60, env=env,
    )


def write_executable(path: Path, content: str):
    path.write_text(content, encoding="utf-8")
    path.chmod(0o700)


def stamp(days_ago: int) -> str:
    value = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return value.strftime("%Y%m%dT%H%M%SZ")


def main():
    for command in ("age", "age-keygen"):
        if not shutil.which(command):
            raise RuntimeError(f"La prueba requiere el programa {command}.")
    with tempfile.TemporaryDirectory(prefix="central-offsite-") as temporary:
        root = Path(temporary)
        source_data = root / "source-data"
        source_data.mkdir(mode=0o700)
        source_config_dir = root / "source-etc"
        source_config_dir.mkdir(mode=0o700)
        source_config = source_config_dir / "config.php"
        setup = subprocess.run(
            ["php", str(SETUP), f"--config={source_config}", f"--data-dir={source_data}",
             "--base-url=https://central.example.test", "--school=Centro ficticio",
             "--name=Administradora de pruebas", "--email=admin@example.test",
             "--password-stdin"],
            input="ClaveFicticiaSoloPruebas123!\n", capture_output=True, text=True, timeout=30,
        )
        assert setup.returncode == 0, setup.stderr
        (source_data / "packages" / "curso.zip").write_bytes(b"contenido ficticio recuperable")

        identity = root / "age-identity.txt"
        generated = subprocess.run(
            ["age-keygen", "-o", str(identity)], capture_output=True, text=True, timeout=15,
        )
        assert generated.returncode == 0, generated.stderr
        public_key = next(
            line.split(": ", 1)[1]
            for line in identity.read_text(encoding="utf-8").splitlines()
            if line.startswith("# public key: ")
        )

        local_dir = root / "local-backups"
        local_dir.mkdir(mode=0o700)
        remote_dir = root / "offsite-store"
        remote_dir.mkdir(mode=0o700)
        old_name = f"central-{stamp(36)}.tar.gz.age"
        old_archive = remote_dir / old_name
        old_archive.write_bytes(b"copia vencida")
        (remote_dir / (old_name + ".sha256")).write_text("checksum antiguo\n")
        expired_target = root / "archivo-externo.txt"
        expired_target.write_text("no borrar")
        expired_link = remote_dir / f"central-{stamp(37)}.tar.gz.age"
        expired_link.symlink_to(expired_target)
        expired_directory = remote_dir / f"central-{stamp(38)}.tar.gz.age"
        expired_directory.mkdir()
        recent_name = f"central-{stamp(20)}.tar.gz.age"
        (remote_dir / recent_name).write_bytes(b"copia reciente")
        unrelated = remote_dir / "no-borrar.txt"
        unrelated.write_text("conservar")

        mock_bin = root / "mock-bin"
        mock_bin.mkdir()
        write_executable(
            mock_bin / "ssh",
            """#!/bin/sh
while [ "$#" -gt 0 ]; do
    if [ "$1" = "--" ]; then
        shift
        break
    fi
    shift
done
shift
exec sh -c "$1"
""",
        )
        write_executable(
            mock_bin / "rsync",
            """#!/usr/bin/env python3
import os, shutil, sys
args = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
if len(args) != 3:
    raise SystemExit("invocación rsync inesperada")
sources, destination = args[:2], args[2]
target_path = destination.split(":", 1)[1].rstrip("/")
for source in sources:
    target = os.path.join(target_path, os.path.basename(source))
    if not os.path.exists(target):
        shutil.copy2(source, target)
""",
        )
        env = os.environ.copy()
        env["PATH"] = str(mock_bin) + os.pathsep + env["PATH"]
        result = run(
            "--config", source_config, "--data-dir", source_data,
            "--local-dir", local_dir, "--recipient", public_key,
            "--ssh-target", "backup@example.test", "--remote-dir", str(remote_dir),
            "--retention-days", "35", "--no-service-control", env=env,
        )
        assert result.returncode == 0, result.stderr
        assert "Copia cifrada y transferida" in result.stdout
        assert "Copias vencidas eliminadas: 1" in result.stdout
        assert not old_archive.exists()
        assert not (remote_dir / (old_name + ".sha256")).exists()
        assert expired_link.is_symlink()
        assert expired_target.read_text(encoding="utf-8") == "no borrar"
        assert expired_directory.is_dir()
        assert (remote_dir / recent_name).exists()
        assert unrelated.read_text(encoding="utf-8") == "conservar"
        assert not list(remote_dir.glob("*.tar.gz"))

        transferred = [
            path for path in remote_dir.glob("central-*.tar.gz.age")
            if path.name != recent_name and path.is_file() and not path.is_symlink()
        ]
        assert len(transferred) == 1
        encrypted_copy = transferred[0]
        assert not encrypted_copy.read_bytes().startswith(b"\x1f\x8b")
        checksum = (remote_dir / (encrypted_copy.name + ".sha256")).read_text().split()[0]
        assert checksum == hashlib.sha256(encrypted_copy.read_bytes()).hexdigest()

        plaintext = root / "downloaded.tar.gz"
        decrypted = subprocess.run(
            ["age", "--decrypt", "--identity", str(identity), "--output",
             str(plaintext), str(encrypted_copy)],
            capture_output=True, text=True, timeout=30,
        )
        assert decrypted.returncode == 0, decrypted.stderr

        recovered_config_dir = root / "recovered-etc"
        recovered_config_dir.mkdir(mode=0o700)
        recovered_data = root / "recovered-data"
        restored = subprocess.run(
            ["python3", str(ROOT / "central/ubuntu/recovery.py"), "restore",
             "--archive", str(plaintext), "--config",
             str(recovered_config_dir / "config.php"), "--data-dir", str(recovered_data)],
            capture_output=True, text=True, timeout=30,
        )
        assert restored.returncode == 0, restored.stderr
        assert (recovered_data / "packages" / "curso.zip").read_bytes() == (
            b"contenido ficticio recuperable"
        )
        config = (recovered_config_dir / "config.php").read_text(encoding="utf-8")
        assert str(recovered_data / "conta-central.sqlite3") in config

    print("Copia externa: cifrado age, transferencia, retención vencida y restauración verificados.")


if __name__ == "__main__":
    main()
