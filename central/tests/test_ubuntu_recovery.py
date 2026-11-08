"""Copia y restauración verificables sin tocar rutas del sistema."""
from pathlib import Path
import os
import shutil
import sqlite3
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
RECOVERY = ROOT / "central/ubuntu/recovery.py"
SETUP = ROOT / "central/ubuntu/setup.php"


def run(*args):
    return subprocess.run(
        ["python3", str(RECOVERY), *map(str, args)],
        capture_output=True, text=True, timeout=30,
    )


def main():
    with tempfile.TemporaryDirectory(prefix="central-recovery-") as temporary:
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
        (source_data / "packages" / "curso.zip").write_bytes(b"paquete ficticio")

        database = source_data / "conta-central.sqlite3"
        key = bytes(range(32))
        (source_data / ".paypal-config.key").write_bytes(key)
        os.chmod(source_data / ".paypal-config.key", 0o600)
        encrypt = r'''
$key=file_get_contents($argv[1]); $nonce=random_bytes(SODIUM_CRYPTO_SECRETBOX_NONCEBYTES);
$plain=json_encode(["client_id"=>"fake-client-id-123","client_secret"=>"fake-secret-456"]);
$payload=base64_encode($nonce.sodium_crypto_secretbox($plain,$nonce,$key));
$db=new PDO("sqlite:".$argv[2]);
$db->exec("CREATE TABLE central_paypal_settings(id INTEGER PRIMARY KEY, encrypted_payload TEXT)");
$stmt=$db->prepare("INSERT INTO central_paypal_settings VALUES(1,?)");$stmt->execute([$payload]);
'''
        encrypted = subprocess.run(
            ["php", "-r", encrypt, str(source_data / ".paypal-config.key"), str(database)],
            capture_output=True, text=True, timeout=15,
        )
        assert encrypted.returncode == 0, encrypted.stderr
        (source_data / ".paypal-config.key").unlink()
        missing_key = run("backup", "--config", source_config, "--data-dir", source_data,
                          "--output", root / "backups-missing-key.tar.gz")
        assert missing_key.returncode and "falta .paypal-config.key" in missing_key.stderr
        (source_data / ".paypal-config.key").write_bytes(key)
        os.chmod(source_data / ".paypal-config.key", 0o600)

        backups = root / "backups"
        backups.mkdir(mode=0o700)
        archive = backups / "central.tar.gz"
        result = run("backup", "--config", source_config, "--data-dir", source_data, "--output", archive)
        assert result.returncode == 0, result.stderr
        assert archive.stat().st_mode & 0o077 == 0
        assert run("backup", "--config", source_config, "--data-dir", source_data, "--output", archive).returncode

        target_config_dir = root / "recovered-etc"
        target_config_dir.mkdir(mode=0o700)
        target_data = root / "recovered-data"
        restore = run("restore", "--archive", archive, "--config",
                      target_config_dir / "config.php", "--data-dir", target_data)
        assert restore.returncode == 0, restore.stderr
        assert "clave privada de PayPal también se restauró" in restore.stdout
        assert (target_data / "packages" / "curso.zip").read_bytes() == b"paquete ficticio"
        assert (target_data / ".paypal-config.key").read_bytes() == key
        for path in (target_config_dir / "config.php", target_data / "conta-central.sqlite3",
                     target_data / ".paypal-config.key", target_data / "packages" / "curso.zip"):
            assert path.stat().st_mode & 0o077 == 0, path

        php_check = r'''
$c=require $argv[1]; $key=file_get_contents(dirname($c["db_path"])."/.paypal-config.key");
$db=new PDO("sqlite:".$c["db_path"]);
$payload=$db->query("SELECT encrypted_payload FROM central_paypal_settings WHERE id=1")->fetchColumn();
$bytes=base64_decode($payload,true); $nonce=substr($bytes,0,SODIUM_CRYPTO_SECRETBOX_NONCEBYTES);
$plain=sodium_crypto_secretbox_open(substr($bytes,SODIUM_CRYPTO_SECRETBOX_NONCEBYTES),$nonce,$key);
if($plain===false) exit(2); $c=json_decode($plain,true);
if(($c["client_id"]??"")!=="fake-client-id-123" || ($c["client_secret"]??"")!=="fake-secret-456") exit(3);
$integrity=$db->query("PRAGMA integrity_check")->fetchColumn(); if($integrity!=="ok") exit(4);
echo "credencial cifrada recuperable; SQLite íntegro";
'''
        verified = subprocess.run(
            ["php", "-r", php_check, str(target_config_dir / "config.php")],
            capture_output=True, text=True, timeout=15,
        )
        assert verified.returncode == 0 and "SQLite íntegro" in verified.stdout, verified.stderr

        original_config = source_config.read_bytes()
        original_database = database.read_bytes()
        overwrite = run("restore", "--archive", archive, "--config", source_config,
                        "--data-dir", source_data)
        assert overwrite.returncode and "ya existe" in overwrite.stderr
        assert source_config.read_bytes() == original_config
        assert database.read_bytes() == original_database
        assert (source_data / "packages" / "curso.zip").read_bytes() == b"paquete ficticio"

        # A damaged archive is rejected before any destination is created.
        damaged = root / "damaged.tar.gz"
        damaged_bytes = bytearray(archive.read_bytes())
        damaged_bytes[len(damaged_bytes) // 2] ^= 0xFF
        damaged.write_bytes(damaged_bytes)
        other_config_dir = root / "other-etc"
        other_config_dir.mkdir()
        other_data = root / "other-data"
        bad_restore = run("restore", "--archive", damaged, "--config",
                          other_config_dir / "config.php", "--data-dir", other_data)
        assert bad_restore.returncode and not other_data.exists()

    print("Recuperación Central: SQLite, paquetes, config privada y clave PayPal; aislada y sin sobrescritura.")


if __name__ == "__main__":
    main()
