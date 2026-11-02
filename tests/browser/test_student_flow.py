"""Actual Keycloak student journey and cross-student denial at three viewports."""

import json
import os
import re
from pathlib import Path
from threading import Thread
from uuid import uuid4

import pytest
from dotenv import dotenv_values
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from app import create_app
from app.repositories.fixtures import fixture_id
from scripts.database_setup import local_client
from scripts.run_local import SafeRequestHandler

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(os.getenv("RUN_BROWSER") != "1", reason="Explicit local browser test"),
]
ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = (ROOT / os.getenv("STUDENT_EVIDENCE_DIR", "runtime/student-browser-evidence")).resolve()
if not any(EVIDENCE.is_relative_to(ROOT / base) for base in ["runtime", "docs/evidence"]):
    raise ValueError("Invalid evidence destination.")


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
@pytest.mark.parametrize("width", [390, 768, 1440])
def test_real_student_submission_and_isolation(engine, width):
    values = dict(dotenv_values(ROOT / ".env"))
    values.update(
        APP_ENV="testing",
        MONGODB_DATABASE="student_support_test",
        APP_BASE_URL="http://127.0.0.1:5051",
        OIDC_CLIENT_ID="support-test",
    )
    app = create_app(values)
    app.extensions["mongo"].close()
    web = local_client(values, "web_testing")
    maintenance = local_client(values, "testing")
    app.extensions["mongo"] = web
    db = maintenance.student_support_test
    credentials = json.loads((ROOT / "runtime/synthetic-logins.json").read_text())
    actor = fixture_id("student_a")
    originals = list(db.cases.find({"student_id": actor}, {"archive_state": 1}))
    db.cases.update_many(
        {"_id": {"$in": [r["_id"] for r in originals]}}, {"$set": {"archive_state": "archived"}}
    )
    marker = "Synthetic browser request " + uuid4().hex
    narrative = (
        marker
        + "\n<script>window.syntheticExecuted=true</script>\nI would like help with living costs."
    )
    request_ids = []
    server = make_server("127.0.0.1", 5051, app, request_handler=SafeRequestHandler, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    def login(page, name):
        page.goto("http://127.0.0.1:5051/sign-in")
        page.locator("#username").fill(credentials[name]["username"])
        page.locator("#password").fill(credentials[name]["password"])
        page.locator("#kc-login").click()
        page.wait_for_url("http://127.0.0.1:5051/account", timeout=10000)

    def capture(page, name):
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(EVIDENCE / f"{engine}-{width}-{name}.png"), full_page=True)

    try:
        with sync_playwright() as pw:
            browser = getattr(pw, engine).launch()
            context = browser.new_context(
                viewport={"width": width, "height": 1000},
                locale="en-GB",
                timezone_id="Europe/London",
            )
            page = context.new_page()
            page.on(
                "response",
                lambda response: request_ids.append(response.headers.get("x-request-id", "")),
            )
            login(page, "student_a")
            page.get_by_role("link", name="Open your requests").click()
            expect(page.get_by_role("heading", name="No support requests yet")).to_be_visible()
            capture(page, "empty")
            page.get_by_role("link", name="New support request", exact=True).click()
            expect(
                page.get_by_role("heading", name="What would you like support with?")
            ).to_be_visible()
            page.locator("#category").select_option("finance")
            page.locator("form.request-form").evaluate("form => form.noValidate=true")
            page.get_by_role("button", name="Send support request").click()
            expect(page.get_by_role("heading", name="Check your request")).to_be_visible()
            assert page.locator("#description").get_attribute("aria-invalid") == "true"
            capture(page, "validation")
            page.locator("#description").fill(narrative)
            capture(page, "form")
            key = page.locator("[name=submission_key]").input_value()
            csrf = page.locator("[name=csrf_token]").input_value()
            page.get_by_role("button", name="Send support request").click()
            page.wait_for_url(re.compile(r"/cases/[0-9a-f-]+\?submitted=1"), timeout=10000)
            expect(page.get_by_role("heading", name="Your request is recorded")).to_be_visible()
            assert page.locator(".request-description").inner_text() == narrative
            assert (
                page.locator("script").count() == 0
                and page.evaluate("window.syntheticExecuted") is None
            )
            case_url = page.url.split("?")[0]
            capture(page, "confirmation")
            # A lost response/repeated POST returns the same case, not another record.
            replay = page.request.post(
                "http://127.0.0.1:5051/cases/new",
                form={
                    "csrf_token": csrf,
                    "submission_key": key,
                    "category": "finance",
                    "description": narrative,
                },
                max_redirects=0,
            )
            assert replay.status == 303 and replay.headers["location"].split("?")[
                0
            ] == case_url.replace("http://127.0.0.1:5051", "")
            page.get_by_role("link", name="Your requests", exact=True).first.click()
            assert page.locator("article.case-card").count() == 1
            capture(page, "overview")
            assert page.evaluate("Object.keys(localStorage)") == []
            assert all(narrative not in c["value"] for c in context.cookies())
            other = browser.new_context(viewport={"width": width, "height": 1000})
            outsider = other.new_page()
            outsider.on(
                "response",
                lambda response: request_ids.append(response.headers.get("x-request-id", "")),
            )
            login(outsider, "student_b")
            response = outsider.goto(case_url)
            assert response.status == 404 and marker not in outsider.content()
            capture(outsider, "denied")
            other.close()
            context.close()
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        case_ids = [
            r["_id"]
            for r in db.cases.find({"student_id": actor, "description": narrative}, {"_id": 1})
        ]
        for name in ["case_events", "notification_outbox"]:
            db[name].delete_many({"case_id": {"$in": case_ids}})
        db.submission_keys.delete_many({"result_id": {"$in": case_ids}})
        db.audit_events.delete_many(
            {"$or": [{"target_id": {"$in": case_ids}}, {"request_id": {"$in": request_ids}}]}
        )
        db.cases.delete_many({"_id": {"$in": case_ids}})
        for row in originals:
            db.cases.update_one(
                {"_id": row["_id"]}, {"$set": {"archive_state": row["archive_state"]}}
            )
        web.close()
        maintenance.close()
