"""Configuración PayPal real por HTTP, sin cuentas reales ni peticiones a PayPal.

python3 central/tests/test_paypal_settings.py [--browser]
Las credenciales ficticias solo existen en un directorio temporal.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import json
import os
import shutil
import socket
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

from test_cpanel_http import SOURCE, json_request

PASSWORD = "SoloPruebasLocales123!"
CLIENT_ID = "ClientIDFicticioSandbox123"
CLIENT_SECRET = "SecretFicticioNoReal123456789!"


@contextmanager
def fixture():
    with tempfile.TemporaryDirectory(prefix="conta-paypal-test-") as temp:
        root = Path(temp)
        public = root / "www"
        shutil.copytree(SOURCE, public)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        base = f"http://127.0.0.1:{port}"
        config = root / "etc" / "config.php"
        setup = subprocess.run([
            "php", str(SOURCE.parent / "ubuntu/setup.php"),
            "--config=" + str(config), "--data-dir=" + str(root / "data"),
            "--base-url=" + base, "--school=Centro ficticio",
            "--name=Administrador ficticio", "--email=admin@example.test",
            "--password-stdin",
        ], input=PASSWORD + "\n", text=True, capture_output=True)
        assert setup.returncode == 0, setup.stderr
        env = {**os.environ, "CONTA_CONFIG_FILE": str(config)}
        seed = r"""
require $argv[1].'/bootstrap.php';
$db=db();
$db->prepare('INSERT INTO schools(name) VALUES(?)')->execute(['Otro centro ficticio']);
foreach ([['teacher@example.test','teacher',1],['student@example.test','student',1],
          ['admin-otro@example.test','admin',2]] as [$email,$role,$school]) {
 $db->prepare('INSERT INTO users(school_id,email,display_name,role,passhash) VALUES(?,?,?,?,?)')
    ->execute([$school,$email,'Prueba '.$role,$role,password_hash($argv[2],PASSWORD_DEFAULT)]);
}
"""
        subprocess.run(["php", "-r", seed, str(public), PASSWORD], env=env, check=True)
        log = root / "server.log"
        with log.open("w+") as output:
            proc = subprocess.Popen([
                "php", "-S", f"127.0.0.1:{port}", "-t", str(public),
                str(SOURCE.parent / "ubuntu/dev-router.php"),
            ], env=env, stdout=output, stderr=output)
            try:
                for _ in range(80):
                    try:
                        json_request(base, "health")
                        break
                    except (OSError, AssertionError, json.JSONDecodeError):
                        time.sleep(.1)
                else:
                    raise AssertionError("No arranca el servidor temporal.")
                yield base, root, public, env
            finally:
                proc.terminate()
                proc.wait(timeout=10)
                output.flush()
                assert CLIENT_SECRET not in log.read_text(), "El secreto apareció en el registro."


def login(base, email):
    return json_request(base, "login", {"email": email, "password": PASSWORD})["token"]


def test_http(base, root, public, env):
    owner = login(base, "admin@example.test")
    tokens = [login(base, email) for email in
              ("teacher@example.test", "student@example.test", "admin-otro@example.test")]
    json_request(base, "paypal_settings", expected=401)
    for token in tokens:
        for route, body in (("paypal_settings", None), ("paypal_settings", {}),
                            ("paypal_test", {}), ("paypal_delete", {})):
            json_request(base, route, body, token, expected=403)
    initial = json_request(base, "paypal_settings", token=owner)["settings"]
    assert initial == {"configured": False, "environment": "sandbox", "revision": "none"}
    json_request(base, "paypal_test", {}, owner, expected=409)
    json_request(base, "paypal_test", {"expected_revision": "none"}, owner, expected=422)
    json_request(base, "paypal_test", token=owner, expected=405)
    payload = dict(environment="sandbox", client_id=CLIENT_ID,
                   client_secret=CLIENT_SECRET, expected_revision="none")
    for bad in ({"environment": "other"}, {"client_secret": ""}, {"client_id": ""}):
        json_request(base, "paypal_settings", {**payload, **bad}, owner, expected=422)
    saved = json_request(base, "paypal_settings", payload, owner)["settings"]
    assert saved["configured"] and saved["verification_status"] == "unverified"
    assert CLIENT_ID not in json.dumps(saved) and CLIENT_SECRET not in json.dumps(saved)
    assert saved["client_id_hint"].endswith(CLIENT_ID[-6:])
    database = root / "data/central.sqlite3"
    # El nombre lo establece el instalador original, no el cliente de pago.
    if not database.exists():
        database = next((root / "data").glob("*.sqlite3"))
    with sqlite3.connect(database) as connection:
        encrypted = connection.execute("SELECT encrypted_payload FROM central_paypal_settings").fetchone()[0]
        assert CLIENT_ID not in encrypted and CLIENT_SECRET not in encrypted
    key = root / "data/.paypal-config.key"
    assert stat.S_IMODE(key.stat().st_mode) == 0o600 and len(key.read_bytes()) == 32
    check = r"""
require $argv[1].'/bootstrap.php';require $argv[1].'/paypal.php';
$data=paypal_settings_decrypt(paypal_settings_row());
if ($data['client_id']!==$argv[2] || $data['client_secret']!==$argv[3]) exit(7);
echo "Cifrado y descifrado correctos\n";
"""
    subprocess.run(["php", "-r", check, str(public), CLIENT_ID, CLIENT_SECRET], env=env, check=True)
    # Un formulario antiguo no puede sobrescribir ni borrar una configuración nueva.
    json_request(base, "paypal_settings", payload, owner, expected=409)
    json_request(base, "paypal_delete", {"expected_revision": "none", "confirm_delete": True}, owner, expected=409)
    preserve = dict(environment="sandbox", expected_revision=saved["revision"], client_id="", client_secret="")
    current = json_request(base, "paypal_settings", preserve, owner)["settings"]
    assert current["revision"] != saved["revision"] and current["client_id_hint"] == saved["client_id_hint"]
    assert current == json_request(base, "paypal_settings", token=login(base, "admin@example.test"))["settings"]
    for bad in ({"client_id": "OtroClientID12345"}, {"environment": "live"},
                {"environment": "live", "confirm_live": True}):
        json_request(base, "paypal_settings", {**preserve, "expected_revision": current["revision"], **bad},
                     owner, expected=422)
    # Guardar credenciales ficticias de producción tampoco llama al proveedor.
    production = {**payload, "environment": "live", "confirm_live": True,
                  "expected_revision": current["revision"]}
    current = json_request(base, "paypal_settings", production, owner)["settings"]
    assert current["environment"] == "live" and current["verification_status"] == "unverified"
    # Perder la clave no debe regenerarla ni descartar el secreto silenciosamente.
    original_key = key.read_bytes()
    key.unlink()
    json_request(base, "paypal_settings", {**production, "expected_revision": current["revision"]},
                 owner, expected=503)
    assert not key.exists()
    key.write_bytes(original_key)
    key.chmod(0o600)
    json_request(base, "paypal_delete", {"expected_revision": current["revision"]}, owner, expected=422)
    deleted = json_request(base, "paypal_delete", {
        "expected_revision": current["revision"], "confirm_delete": True,
    }, owner)["settings"]
    assert deleted["configured"] is False
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM central_paypal_settings").fetchone()[0] == 0
        events = connection.execute("SELECT actor_id,action FROM paypal_config_events").fetchall()
        assert len(events) == 4 and all(actor == 1 for actor, _ in events)
        assert [action for _, action in events] == ["saved", "saved", "saved", "deleted"]
    for path in ("/paypal.php", "/private/.paypal-config.key", "/.paypal-config.key"):
        try:
            urllib.request.urlopen(base + path)
            raise AssertionError("Se expone un recurso privado.")
        except urllib.error.HTTPError as error:
            assert error.code == 404
    classifications = r"""
require $argv[1].'/paypal.php';
$tests=[
 [200,'{"access_token":"ficticio","token_type":"Bearer","expires_in":60}',true,'verified'],
 [401,'{"error":"invalid_client"}',true,'rejected'],
 [403,'sin acceso',true,'rejected'],
 [200,'{"access_token":"ficticio","token_type":"other","expires_in":60}',true,'unavailable'],
 [200,'{"access_token":"ficticio","token_type":"Bearer","expires_in":0}',true,'unavailable'],
 [500,'no json',true,'unavailable'],[200,'{}',false,'unavailable']
];
foreach ($tests as [$code,$body,$ok,$expected]) {
 if(paypal_oauth_result($code,$body,$ok)!==$expected)exit(8);
}
echo "Respuestas OAuth clasificadas sin devolver tokens\n";
"""
    subprocess.run(["php", "-r", classifications, str(public)], check=True)
    print("Configuración PayPal HTTP: permisos, cifrado, conservación, conflictos, entornos, auditoría y borrado OK.")


def test_browser(base):
    from playwright.sync_api import expect, sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_EXECUTABLE") or shutil.which("chromium"),
                                    headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1366, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        def sign_in():
            page.goto(base)
            page.locator("#loginForm input[name=email]").fill("admin@example.test")
            page.locator("#loginForm input[name=password]").fill(PASSWORD)
            page.locator("#loginForm button").click()
            page.locator("#app").wait_for(state="visible")
            page.locator(".side-nav button[data-view='admin']").click()
            page.locator("#paypalSettings").wait_for(state="visible")
        sign_in()
        form = page.locator("#paypalForm")
        form.locator("[name=client_id]").fill(CLIENT_ID)
        form.locator("[name=client_secret]").fill(CLIENT_SECRET)
        form.locator("button").click()
        expect(page.locator("#paypalMessage")).to_contain_text("Configuración guardada")
        assert form.locator("[name=client_secret]").input_value() == ""
        assert form.locator("[name=client_id]").input_value() == ""
        assert CLIENT_SECRET not in page.locator("body").inner_text()
        assert page.locator("#paypalTest").is_enabled()
        capture = os.environ.get("PAYPAL_PREVIEW_SCREENSHOT")
        if capture:
            Path(capture).parent.mkdir(parents=True, exist_ok=True)
            page.locator("#paypalSettings").scroll_into_view_if_needed()
            page.screenshot(path=capture)
        form.locator("[name=client_id]").fill("OtroClientID123")
        assert page.locator("#paypalTest").is_disabled()
        # La actualización general no debe borrar un formulario sin guardar.
        page.locator("#top-refresh").click()
        page.wait_for_timeout(150)
        assert form.locator("[name=client_id]").input_value() == "OtroClientID123"
        page.on("dialog", lambda dialog: dialog.accept())
        page.locator("#paypalReload").click()
        expect(page.locator("#paypalForm [name=client_id]")).to_have_value("")
        # Persistencia real al recargar y volver a iniciar sesión.
        sign_in()
        assert "Sandbox" in page.locator("#paypalSummary").inner_text()
        assert form.locator("[name=client_secret]").input_value() == ""
        page.locator("#paypalDelete").click()
        expect(page.locator("#paypalMessage")).to_contain_text("Credenciales eliminadas")
        assert page.locator("#paypalTest").is_disabled()
        assert not errors, errors
        browser.close()
    print("Panel PayPal en navegador con API/SQLite reales: guardar, recargar, conservar borrador y eliminar OK.")


if __name__ == "__main__":
    with fixture() as (base, root, public, env):
        test_http(base, root, public, env)
        if "--browser" in sys.argv:
            test_browser(base)
