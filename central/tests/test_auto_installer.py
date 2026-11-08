"""Validación inofensiva del instalador Bash; no cambia el sistema."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "central/ubuntu/install.sh"


def run(*args):
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        text=True, capture_output=True, timeout=15,
    )


def main():
    assert SCRIPT.is_file()
    result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    help_text = run("--help")
    assert help_text.returncode == 0 and "--letsencrypt" in help_text.stdout
    common = [
        "--dry-run", "--yes", "--domain=central.example.org",
        "--school=Centro temporal", "--name=Admin temporal",
        "--email=admin@example.org",
    ]
    plan = run(*common, "--letsencrypt")
    assert plan.returncode == 0, plan.stderr
    assert "no se ha instalado nada" in plan.stdout
    assert "/var/www/conta-fp360" in plan.stdout
    assert "Let's Encrypt" in plan.stdout
    assert run("--dry-run", "--domain=localhost", "--school=x", "--name=y",
               "--email=admin@example.org", "--letsencrypt").returncode != 0
    assert run("--dry-run", "--domain=evil;example.org", "--school=x", "--name=y",
               "--email=admin@example.org", "--letsencrypt").returncode != 0
    assert run(*common).returncode != 0, "Sin HTTPS, el instalador no debe continuar."
    assert run(*common, "--letsencrypt", "--admin-password=sensitive").returncode != 0
    assert not (ROOT / "var/lib/conta-fp360").exists()
    with tempfile.TemporaryDirectory(prefix="central-install-tls-") as temp:
        cert = Path(temp) / "fullchain.pem"
        key = Path(temp) / "privkey.pem"
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "3",
            "-keyout", str(key), "-out", str(cert), "-subj", "/CN=central.example.org",
            "-addext", "subjectAltName=DNS:central.example.org",
            "-addext", "extendedKeyUsage=serverAuth",
        ], check=True, capture_output=True, text=True)
        untrusted = run(
            "--dry-run", "--domain=central.example.org", "--school=x", "--name=y",
            "--email=admin@example.org", f"--certificate={cert}", f"--private-key={key}",
        )
        assert untrusted.returncode != 0
        assert "autoridad de confianza" in untrusted.stderr
    print("Autoinstalador: sintaxis, ayuda, prevalidación y ejecución seca correctas; sin cambios del sistema.")


if __name__ == "__main__":
    main()
