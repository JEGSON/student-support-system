"""Isolated actual-browser verification for the Stage 03 synthetic runtime."""

import json
import os
import secrets
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from app import create_app

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(
        os.getenv("RUN_BROWSER") != "1", reason="Set RUN_BROWSER=1 and install the locked browsers"
    ),
]
ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = (ROOT / os.getenv("BROWSER_EVIDENCE_DIR", "runtime/browser-evidence")).resolve()
if not any(EVIDENCE.is_relative_to(ROOT / base) for base in ["runtime", "docs/evidence"]):
    raise ValueError("Browser evidence must stay in the repository's runtime/evidence directories.")
SCREENS = {
    "entry": "/",
    "components": "/_dev/components",
    "student": "/_dev/shell/student",
    "staff": "/_dev/shell/staff",
}


@pytest.fixture(scope="module")
def synthetic_server():
    # Synthetic gallery requires development mode; no connection or real credentials.
    app = create_app(
        dict(
            APP_ENV="development",
            SECRET_KEY=secrets.token_urlsafe(64),
            FLASK_DEBUG="0",
            APP_BASE_URL="http://127.0.0.1:5050",
            MONGODB_URI="mongodb://localhost:27017/?replicaSet=rs0",
            MONGODB_DATABASE="student_support_dev",
            OIDC_CLIENT_ID="support-local",
            OIDC_ISSUER="http://127.0.0.1:8180/realms/student-support",
            EMAIL_HEALTH_URL="http://127.0.0.1:8025/readyz",
        )
    )
    server = make_server("127.0.0.1", 0, app)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join(timeout=5)
    server.server_close()
    app.extensions["mongo"].close()


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
@pytest.mark.parametrize("width", [390, 768, 1440])
def test_responsive_shells_and_components(synthetic_server, engine, width):
    EVIDENCE.joinpath("screenshots").mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = getattr(playwright, engine).launch()
        context = browser.new_context(
            viewport={"width": width, "height": 1000},
            reduced_motion="reduce",
            locale="en-GB",
            timezone_id="Europe/London",
        )
        try:
            requests = []

            def local_only(route):
                if urlsplit(route.request.url).hostname != "127.0.0.1":
                    requests.append(route.request.url)
                    route.abort()
                else:
                    route.continue_()

            context.route("**/*", local_only)
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(type(error).__name__))
            for name, path in SCREENS.items():
                response = page.goto(synthetic_server + path, wait_until="networkidle")
                assert response.status == 200
                expect(page.locator("h1")).to_have_count(1)
                assert page.evaluate("window.innerWidth") == width
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), (
                    f"Overflow: {engine}/{width}/{name}"
                )
                assert page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches")
                assert page.evaluate("document.getAnimations().length") == 0
                page.screenshot(
                    path=str(EVIDENCE / "screenshots" / f"{engine}-{width}-{name}.png"),
                    full_page=True,
                )
                # Keyboard reaches the skip link, whose outline and visibility must render.
                page.keyboard.press("Alt+Tab" if engine == "webkit" else "Tab")
                skip = page.get_by_role("link", name="Skip to content")
                expect(skip).to_be_focused()
                assert skip.bounding_box()["y"] >= 0
                assert skip.evaluate("e => getComputedStyle(e).outlineStyle") != "none"
                if name == "staff":
                    for label in ["Reference", "Category", "Submitted", "Status", "Team"]:
                        assert label.lower() in page.locator("main").inner_text().lower()
                    expect(page.locator(".queue-row:not(.heading)").first).to_contain_text(
                        "SS-DEMO-001"
                    )
                if name == "components":
                    expect(page.get_by_role("button", name="Submitting request…")).to_be_disabled()
                    field = page.get_by_label("Tell us what is happening (required)")
                    field.focus()
                    assert field.evaluate("e => getComputedStyle(e).outlineWidth") == "3px"
                    assert field.get_attribute("aria-invalid") == "true"
                if name == "components":
                    page.screenshot(
                        path=str(EVIDENCE / "screenshots" / f"{engine}-{width}-focus.png"),
                        full_page=True,
                    )
            assert not requests, f"Unexpected external requests: {requests}"
            assert not errors
            (EVIDENCE / f"{engine}-{width}.json").write_text(
                json.dumps(
                    {
                        "browser": engine,
                        "version": browser.version,
                        "width": width,
                        "screens": list(SCREENS),
                        "reduced_motion": "reduce",
                        "horizontal_overflow": False,
                        "keyboard_focus": "checked",
                        "external_requests": 0,
                        "page_errors": 0,
                    },
                    indent=2,
                )
                + "\n"
            )
        finally:
            context.close()
            browser.close()
