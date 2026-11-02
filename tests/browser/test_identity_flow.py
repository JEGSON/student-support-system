"""Real Keycloak code/PKCE login and local logout at three viewport widths."""

import json
import os
import re
from pathlib import Path
from threading import Thread

import pytest
from dotenv import dotenv_values
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

from app import create_app
from scripts.database_setup import local_client
from scripts.run_local import SafeRequestHandler

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(os.getenv("RUN_BROWSER") != "1", reason="Explicit isolated browser test"),
]
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "actor,expected_context", [("student_a", "student"), ("administrator", "admin")]
)
@pytest.mark.parametrize("engine", ["chromium", "webkit"])
@pytest.mark.parametrize("width", [390, 768, 1440])
def test_real_provider_login(width, engine, actor, expected_context):
    values = dict(dotenv_values(ROOT / ".env"))
    values.update(
        APP_ENV="testing",
        MONGODB_DATABASE="student_support_test",
        APP_BASE_URL="http://127.0.0.1:5051",
        OIDC_CLIENT_ID="support-test",
    )
    app = create_app(values)
    app.extensions["mongo"].close()
    client = local_client(values, "testing")
    app.extensions["mongo"] = client
    credentials = json.loads((ROOT / "runtime/synthetic-logins.json").read_text())[actor]
    server = make_server("127.0.0.1", 5051, app, request_handler=SafeRequestHandler, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    folder = ROOT / "docs/evidence/stages-05-06/browser"
    folder.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as pw:
            browser = getattr(pw, engine).launch()
            page = browser.new_page(viewport={"width": width, "height": 900})
            page.goto("http://127.0.0.1:5051/sign-in?next=https://evil.invalid")
            assert "code_challenge_method=S256" in page.url and "code_challenge=" in page.url
            page.locator("#username").fill(credentials["username"])
            page.locator("#password").fill(credentials["password"])
            page.locator("#kc-login").click()
            try:
                page.wait_for_url("http://127.0.0.1:5051/account", timeout=10000)
            except Exception:
                from urllib.parse import urlsplit

                raise AssertionError(
                    {
                        "path": urlsplit(page.url).path,
                        "headings": page.locator(
                            "h1,h2,#kc-page-title,.alert-error"
                        ).all_text_contents(),
                        "inputs": page.locator("input").evaluate_all("els => els.map(e => e.name)"),
                    }
                ) from None
            assert page.get_by_role("heading", name="Your support space").is_visible()
            assert page.locator("#context").input_value() == expected_context
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert page.locator("select").evaluate_all(
                "els => els.every(e => e.getBoundingClientRect().height >= 44)"
            )
            cookies = page.context.cookies("http://127.0.0.1:5051")
            cookie = next(c for c in cookies if c["name"] == "support_session")
            assert (
                cookie["httpOnly"]
                and cookie["sameSite"] == "Lax"
                and re.fullmatch("[A-Za-z0-9_-]{43}", cookie["value"])
            )
            assert page.evaluate("Object.keys(localStorage)") == []
            page.screenshot(
                path=str(folder / f"account-{actor}-{engine}-{width}.png"), full_page=True
            )
            if actor == "administrator":
                page.get_by_role("link", name="Manage service access").click()
                assert page.get_by_role("heading", name="Manage service access").is_visible()
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                assert page.locator("select").evaluate_all(
                    "els => els.every(e => e.getBoundingClientRect().height >= 44)"
                )
                page.screenshot(path=str(folder / f"access-{engine}-{width}.png"), full_page=True)
                page.get_by_role("link", name="Return to your account").click()
            else:
                assert page.request.get("http://127.0.0.1:5051/access").status == 403
            page.get_by_role("button", name="Sign out of Student Support").click()
            assert page.get_by_role("heading", name="You have signed out").is_visible()
            assert not any(
                c["name"] == "support_session"
                for c in page.context.cookies("http://127.0.0.1:5051")
            )
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        client.close()
