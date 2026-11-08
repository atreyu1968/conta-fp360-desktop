"""Restablecimiento CLI de administrador sin alterar los datos de Central."""
from pathlib import Path
import hashlib
import importlib.util
import fcntl
import os
import pty
import select
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import termios

ROOT = Path(__file__).resolve().parents[2]
SETUP = ROOT / "central/ubuntu/setup.php"
RECOVERY = ROOT / "central/ubuntu/recovery.py"
spec = importlib.util.spec_from_file_location("central_recovery", RECOVERY)
recovery = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(recovery)

OLD_PASSWORD = "ClaveFicticiaSoloPruebas123!"
NEW_PASSWORD = "OtraClaveFicticiaSoloPruebas456!"
INTERACTIVE_PASSWORD = "ClaveInteractivaSoloPruebas789!"
ADMIN_EMAIL = "admin@example.test"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def php_password_matches(database: Path, email: str, password: str) -> bool:
    code = (
        '$db=new PDO("sqlite:".$argv[1]);'
        '$s=$db->prepare("SELECT passhash FROM users WHERE email=?");'
        '$s->execute([$argv[2]]); $h=$s->fetchColumn();'
        'exit($h && password_verify(stream_get_contents(STDIN),$h) ? 0 : 1);'
    )
    result = subprocess.run(
        ["php", "-r", code, str(database), email],
        input=password, capture_output=True, text=True, timeout=15,
    )
    return result.returncode == 0


def run_interactive_reset(config: Path, email: str, password: str) -> bytes:
    master, slave = pty.openpty()

    def attach_terminal():
        os.setsid()
        fcntl.ioctl(slave, termios.TIOCSCTTY, 0)

    process = subprocess.Popen(
        [sys.executable, str(RECOVERY), "reset-password",
         f"--config={config}", f"--email={email}"],
        stdin=slave, stdout=slave, stderr=slave, close_fds=True,
        pass_fds=(slave,), preexec_fn=attach_terminal,
    )
    os.close(slave)
    transcript = bytearray()

    def wait_for(prompt: bytes):
        while prompt not in transcript:
            ready, _, _ = select.select([master], [], [], 10)
            assert ready, f"No apareció el prompt esperado: {prompt!r}"
            try:
                transcript.extend(os.read(master, 4096))
            except OSError:
                break
        assert prompt in transcript, bytes(transcript)

    try:
        wait_for(b"Nueva contrase\xc3\xb1a del administrador")
        os.write(master, password.encode() + b"\n")
        wait_for(b"Repita la contrase\xc3\xb1a:")
        os.write(master, password.encode() + b"\n")
        while process.poll() is None:
            ready, _, _ = select.select([master], [], [], 0.2)
            if ready:
                try:
                    transcript.extend(os.read(master, 4096))
                except OSError:
                    break
        process.wait(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)
    assert process.returncode == 0, bytes(transcript)
    return bytes(transcript)


def test_password_recovery():
    with tempfile.TemporaryDirectory(prefix="central-password-recovery-") as temporary:
        root = Path(temporary)
        source = ROOT / "central"
        code = root / "central"
        shutil.copytree(source, code)
        data = root / "data"
        data.mkdir(mode=0o700)
        config = root / "etc" / "config.php"
        config.parent.mkdir(mode=0o700)
        setup = subprocess.run(
            ["php", str(code / "ubuntu/setup.php"), f"--config={config}",
             f"--data-dir={data}", "--base-url=https://central.example.test",
             "--school=Centro ficticio", "--name=Administradora de pruebas",
             f"--email={ADMIN_EMAIL}", "--password-stdin"],
            input=OLD_PASSWORD, capture_output=True, text=True, timeout=30,
        )
        assert setup.returncode == 0, setup.stderr

        database = data / "conta-central.sqlite3"
        package = data / "packages" / "curso.zip"
        package.write_bytes(b"paquete ficticio inalterable")
        key = bytes(range(32))
        (data / ".paypal-config.key").write_bytes(key)
        os.chmod(data / ".paypal-config.key", 0o600)
        encrypted_payload = "dGVzdC1jcmVkZW50aWFsLWNpcGhlcnRleHQ="
        with sqlite3.connect(database) as db:
            db.execute("PRAGMA foreign_keys=ON")
            admin_id = db.execute(
                "SELECT id FROM users WHERE email=?", (ADMIN_EMAIL,)
            ).fetchone()[0]
            school_id = db.execute(
                "SELECT school_id FROM users WHERE id=?", (admin_id,)
            ).fetchone()[0]
            db.executemany(
                "INSERT INTO users(school_id,email,display_name,role,passhash) VALUES(?,?,?,?,?)",
                [
                    (school_id, "docente@example.test", "Docente", "teacher", "irrelevant"),
                    (school_id, "alumno@example.test", "Alumno", "student", "irrelevant"),
                ],
            )
            teacher_id = db.execute(
                "SELECT id FROM users WHERE email='docente@example.test'"
            ).fetchone()[0]
            student_id = db.execute(
                "SELECT id FROM users WHERE email='alumno@example.test'"
            ).fetchone()[0]
            db.execute(
                "INSERT INTO groups(school_id,name,academic_year,teacher_id) VALUES(?,?,?,?)",
                (school_id, "Aula de prueba", "2026-2027", teacher_id),
            )
            group_id = db.execute("SELECT id FROM groups").fetchone()[0]
            db.execute(
                "INSERT INTO enrollments(group_id,student_id) VALUES(?,?)",
                (group_id, student_id),
            )
            db.execute(
                "INSERT INTO tokens(hash,user_id,expires_at,created_at) VALUES(?,?,?,?)",
                ("token-hash-to-revoke", admin_id, 4102444800, 1),
            )
            db.execute(
                """CREATE TABLE central_paypal_settings(
                    id INTEGER PRIMARY KEY CHECK(id=1), environment TEXT NOT NULL,
                    client_hint TEXT NOT NULL, encrypted_payload TEXT NOT NULL,
                    revision TEXT NOT NULL, verification_status TEXT NOT NULL,
                    checked_at TEXT, updated_at TEXT NOT NULL,
                    updated_by INTEGER NOT NULL REFERENCES users(id))"""
            )
            db.execute(
                """INSERT INTO central_paypal_settings
                   (id,environment,client_hint,encrypted_payload,revision,
                    verification_status,updated_at,updated_by)
                   VALUES(1,'sandbox','cuenta de prueba',?,'revision-1',
                          'unverified','2026-11-08',?)""",
                (encrypted_payload, admin_id),
            )

        with sqlite3.connect(database) as db:
            preserved_before = {
                "schools": db.execute("SELECT * FROM schools ORDER BY id").fetchall(),
                "groups": db.execute("SELECT * FROM groups ORDER BY id").fetchall(),
                "enrollments": db.execute(
                    "SELECT * FROM enrollments ORDER BY group_id,student_id"
                ).fetchall(),
                "users": db.execute(
                    "SELECT id,school_id,email,display_name,role,active FROM users ORDER BY id"
                ).fetchall(),
                "paypal": db.execute(
                    "SELECT * FROM central_paypal_settings ORDER BY id"
                ).fetchall(),
            }
        config_before = digest(config)
        package_before = digest(package)
        key_before = digest(data / ".paypal-config.key")

        # The secret is supplied to PHP only through stdin, never in argv or output.
        from unittest.mock import patch
        with patch.object(recovery.subprocess, "run", wraps=subprocess.run) as run_spy:
            result = recovery.set_admin_password(database, ADMIN_EMAIL, NEW_PASSWORD)
        command = run_spy.call_args.args[0]
        assert NEW_PASSWORD not in command
        assert NEW_PASSWORD not in result.stdout + result.stderr
        assert result.returncode == 0, result.stderr
        assert "sesiones" in result.stdout
        assert php_password_matches(database, ADMIN_EMAIL, NEW_PASSWORD)
        assert not php_password_matches(database, ADMIN_EMAIL, OLD_PASSWORD)

        with sqlite3.connect(database) as db:
            preserved_after = {
                "schools": db.execute("SELECT * FROM schools ORDER BY id").fetchall(),
                "groups": db.execute("SELECT * FROM groups ORDER BY id").fetchall(),
                "enrollments": db.execute(
                    "SELECT * FROM enrollments ORDER BY group_id,student_id"
                ).fetchall(),
                "users": db.execute(
                    "SELECT id,school_id,email,display_name,role,active FROM users ORDER BY id"
                ).fetchall(),
                "paypal": db.execute(
                    "SELECT * FROM central_paypal_settings ORDER BY id"
                ).fetchall(),
            }
            assert db.execute("SELECT COUNT(*) FROM tokens").fetchone()[0] == 0
            assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert preserved_after == preserved_before
        assert digest(config) == config_before
        assert digest(package) == package_before
        assert digest(data / ".paypal-config.key") == key_before

        # The real terminal flow does not echo the typed password.
        transcript = run_interactive_reset(config, ADMIN_EMAIL, INTERACTIVE_PASSWORD)
        assert INTERACTIVE_PASSWORD.encode() not in transcript
        assert b"Contrase\xc3\xb1a actualizada" in transcript
        assert php_password_matches(database, ADMIN_EMAIL, INTERACTIVE_PASSWORD)

        # Non-interactive invocations must not consume a password piped to stdin.
        before_hash = sqlite3.connect(database).execute(
            "SELECT passhash FROM users WHERE email=?", (ADMIN_EMAIL,)
        ).fetchone()[0]
        no_tty = subprocess.run(
            [sys.executable, str(RECOVERY), "reset-password",
             f"--config={config}", f"--email={ADMIN_EMAIL}"],
            input="No debe utilizarse esta clave", capture_output=True, text=True, timeout=15,
        )
        after_hash = sqlite3.connect(database).execute(
            "SELECT passhash FROM users WHERE email=?", (ADMIN_EMAIL,)
        ).fetchone()[0]
        assert no_tty.returncode != 0
        assert "terminal interactiva" in no_tty.stderr
        assert "No debe utilizarse" not in no_tty.stdout + no_tty.stderr
        assert before_hash == after_hash

    print("Recuperación de contraseña: hash actualizado, sesiones revocadas y datos Central/PayPal preservados.")


if __name__ == "__main__":
    test_password_recovery()
