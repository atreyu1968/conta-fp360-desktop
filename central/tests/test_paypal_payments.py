"""Cobros PayPal aislados: datos ficticios, sin llamadas externas ni cuentas reales."""
from __future__ import annotations

from pathlib import Path
import json
import os
import shutil
import sqlite3
import subprocess
import sys

from test_paypal_settings import CLIENT_ID, CLIENT_SECRET, fixture, json_request, login


def run(base, root, public, env):
    owner = login(base, "admin@example.test")
    teacher = login(base, "teacher@example.test")
    student = login(base, "student@example.test")
    initial = json_request(base, "paypal_settings", token=owner)["settings"]
    payload = {
        "environment": "sandbox",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "merchant_id": "MerchantSandbox123",
        "webhook_id": "WebhookSandbox123",
        "expected_revision": initial["revision"],
    }
    saved = json_request(base, "paypal_settings", payload, owner)["settings"]
    assert saved["webhook_configured"] and saved["merchant_configured"]
    assert CLIENT_SECRET not in json.dumps(saved)
    assert json_request(base, "paypal_license", token=teacher)["license"] is None
    json_request(base, "paypal_license", token=owner, expected=403)
    json_request(base, "paypal_license", token=student, expected=403)
    json_request(base, "paypal_order", {
        "classrooms": 1, "request_id": "fake-request-key-0123456789",
    }, owner, expected=403)

    # Un webhook sin cabeceras criptográficas se rechaza antes de tratar eventos.
    json_request(base, "paypal_webhook", {
        "id": "EVENT-FAKE-UNSIGNED", "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {},
    }, expected=401)

    database = root / "data/central.sqlite3"
    if not database.exists():
        database = next((root / "data").glob("*.sqlite3"))
    with sqlite3.connect(database) as connection:
        # Marcar la configuración como verificada solo dentro de esta fixture
        # permite demostrar que el bloqueo de producción ocurre antes de la red.
        connection.execute(
            "UPDATE central_paypal_settings SET environment='live',verification_status='verified'"
        )
        connection.commit()
    json_request(base, "paypal_order", {
        "classrooms": 1, "request_id": "fake-request-key-0123456789",
    }, teacher, expected=503)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM paypal_orders").fetchone()[0] == 0
        connection.execute(
            "UPDATE central_paypal_settings SET environment='sandbox',verification_status='verified'"
        )
        connection.commit()

    result = subprocess.run(
        ["php", str(Path(__file__).with_name("paypal_payments_assertions.php"))],
        env=env, text=True, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    print(result.stdout.strip())
    print("PayPal HTTP: separación de roles, configuración protegida, rechazo de firmas inválidas y bloqueo de producción OK.")


def test_browser(base):
    from playwright.sync_api import expect, sync_playwright
    executable = os.environ.get("CHROMIUM_EXECUTABLE") or shutil.which("chromium")
    if not executable:
        raise RuntimeError("Indique CHROMIUM_EXECUTABLE para la prueba de navegador.")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=executable, headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1366, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base)
        page.locator("#loginForm input[name=email]").fill("teacher@example.test")
        page.locator("#loginForm input[name=password]").fill("SoloPruebasLocales123!")
        page.locator("#loginForm button").click()
        page.locator("#app").wait_for(state="visible")
        page.locator("#teacherLicense").wait_for(state="visible")
        expect(page.locator("#licenseSummary")).to_contain_text("No hay una licencia")
        expect(page.locator("#teacherLicense")).to_contain_text("Solo PayPal Sandbox")
        page.locator("#licenseOrderForm button").click()
        expect(page.locator("#licenseMessage")).to_contain_text("credenciales de PayPal")
        expect(page.locator("#licenseOrderForm button")).to_be_enabled()
        assert not errors, errors
        browser.close()
    print("PayPal UI: panel de compra y renovación visible para docente, sin errores de navegador.")


if __name__ == "__main__":
    with fixture() as (base, root, public, env):
        if "--browser" in sys.argv:
            test_browser(base)
        run(base, root, public, env)
