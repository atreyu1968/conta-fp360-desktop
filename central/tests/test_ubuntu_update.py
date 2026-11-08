"""Checks inofensivos para el actualizador de Central en Ubuntu."""
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "central/ubuntu/update.sh"


def main():
    syntax = subprocess.run(["bash", "-n", str(SCRIPT)], text=True, capture_output=True)
    assert syntax.returncode == 0, syntax.stderr

    help_result = subprocess.run(
        ["bash", str(SCRIPT), "--help"], text=True, capture_output=True, timeout=15
    )
    assert help_result.returncode == 0
    assert "--rollback" in help_result.stdout and "No use install.sh" in help_result.stdout

    test = subprocess.run(
        ["bash", str(SCRIPT), "--self-test"], text=True, capture_output=True, timeout=15
    )
    assert test.returncode == 0, test.stderr
    assert "restauró el código anterior" in test.stdout
    assert "verificó SQLite y PayPal" in test.stdout
    assert "no alteró los datos" in test.stdout

    with tempfile.TemporaryDirectory(prefix="central-ubuntu-update-bundle-") as temp:
        bundle_path = Path(temp) / "central.zip"
        result = subprocess.run(
            ["python3", str(ROOT / "scripts/build_ubuntu_bundle.py"), str(bundle_path)],
            text=True,
            capture_output=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        with ZipFile(bundle_path) as bundle:
            names = set(bundle.namelist())
            assert "central/ubuntu/update.sh" in names
            assert "central/ubuntu/install.sh" in names
            assert "central/tests/test_ubuntu_update.py" in names
            assert not any(Path(name).name == "config.php" for name in names)
            assert not any(Path(name).suffix in {".sqlite", ".sqlite3", ".db"} for name in names)
    print("Actualizador Ubuntu: sintaxis, restauración aislada, copia SQLite/PayPal y paquete fuente comprobados.")


if __name__ == "__main__":
    main()
