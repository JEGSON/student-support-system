"""Synthetic provider sign-up, editable own profile and first support request."""

import json
import os
import re
import secrets
from pathlib import Path
from threading import Thread
from uuid import uuid4

import pytest
from dotenv import dotenv_values
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from app import create_app
from app.repositories.fixtures import fixture_id
from scripts.configure_registration import ORIGIN, provider_session
from scripts.database_setup import local_client
from scripts.run_local import SafeRequestHandler

ROOT = Path(__file__).resolve().parents[2]
pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(os.getenv("RUN_BROWSER") != "1", reason="Explicit synthetic browser run"),
]


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
@pytest.mark.parametrize("width", [390, 1440])
def test_student_signup_profile_and_first_case(engine, width):
    values = dict(dotenv_values(ROOT / ".env"))
    app = create_app(
        {
            **values,
            "APP_ENV": "testing",
            "MONGODB_DATABASE": "student_support_test",
            "APP_BASE_URL": "http://127.0.0.1:5051",
            "OIDC_CLIENT_ID": "support-test",
            "SELF_REGISTRATION_ENABLED": "1",
        }
    )
    app.extensions["mongo"].close()
    web = local_client(values, "web_testing")
    maintenance = local_client(values, "testing")
    db = maintenance.student_support_test
    app.extensions["mongo"] = web
    username = "demo_" + uuid4().hex
    password = "Demo9" + secrets.token_urlsafe(24)
    server = make_server("127.0.0.1", 5051, app, request_handler=SafeRequestHandler, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    evidence = ROOT / "docs/evidence/account-profiles"
    evidence.mkdir(exist_ok=True)
    report = {}
    try:
        with sync_playwright() as pw:
            browser = getattr(pw, engine).launch()
            context = browser.new_context(viewport={"width": width, "height": 1000}, locale="en-GB")
            page = context.new_page()
            page.goto("http://127.0.0.1:5051/")
            page.get_by_role("link", name="Create a student account").click()
            page.screenshot(path=str(evidence / f"{engine}-{width}-start.png"), full_page=True)
            with page.expect_response(
                lambda r: r.url.endswith("/register/start") and r.request.method == "GET"
            ) as outgoing:
                page.get_by_role("link", name="Continue to account creation").click()
            destination = outgoing.value.headers["location"]
            assert all(
                part in destination for part in ["prompt=create", "code_challenge_method=S256"]
            )
            page.locator("#username").wait_for(state="visible")
            page.locator("#username").fill(username)
            page.locator("#firstName").fill("Synthetic")
            page.locator("#lastName").fill("New Student")
            page.locator("#email").fill(username + "@example.com")
            page.locator("#password").fill(password)
            page.locator("#password-confirm").fill(password)
            page.locator("input[type=submit]").click()
            expect(page.locator("#email")).to_have_attribute("aria-invalid", "true")
            page.locator("#email").fill(username + "@example.invalid")
            page.locator("#password").fill(password)
            page.locator("#password-confirm").fill(password)
            page.locator("input[type=submit]").click()
            page.wait_for_url("http://127.0.0.1:5051/account", timeout=15000)
            expect(page.get_by_role("heading", name="Your support space")).to_be_visible()
            page.get_by_role("link", name="View and edit your profile").click()
            page.locator("#display_name").fill("Synthetic Alex")
            page.locator("#course_label").fill("Fictional Computer Science")
            page.get_by_role("button", name="Save profile").click()
            page.wait_for_url("http://127.0.0.1:5051/account/profile?saved=1")
            expect(page.get_by_role("heading", name="Profile saved")).to_be_visible()
            expect(page.locator("#display_name")).to_have_value("Synthetic Alex")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            axe = ROOT / "runtime/accessibility/node_modules/axe-core/axe.min.js"
            page.evaluate(axe.read_text())
            result = page.evaluate(
                "async()=>await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}})"
            )
            assert not result["violations"], [(v["id"], v["impact"]) for v in result["violations"]]
            report["profile_axe_violations"] = len(result["violations"])
            page.screenshot(path=str(evidence / f"{engine}-{width}-profile.png"), full_page=True)
            page.get_by_role("link", name="Your requests", exact=True).click()
            page.get_by_role("link", name="New support request", exact=True).click()
            page.locator("#category").select_option("finance")
            page.locator("#description").fill("Synthetic first request after self-registration.")
            page.get_by_role("button", name="Send support request", exact=True).click()
            page.wait_for_url(re.compile("/cases/[0-9a-f-]+\\?submitted=1"))
            case_id = page.url.split("/cases/")[1].split("?")[0]
            created = db.cases.find_one({"_id": case_id})
            user = db.users.find_one({"_id": created["student_id"]})
            assert user["global_roles"] == ["student"] and user["display_name"] == "Synthetic Alex"
            denied = page.request.get("http://127.0.0.1:5051/cases/" + fixture_id("case_a"))
            assert denied.status == 404 and "SYNTHETIC_NOTE" not in denied.text()
            denied = page.request.get("http://127.0.0.1:5051/access")
            assert denied.status == 403
            context.clear_cookies()
            page.goto("http://127.0.0.1:5051/sign-in")
            page.locator("#username").fill(username)
            page.locator("#password").fill(password)
            page.locator("#kc-login").click()
            page.wait_for_url("http://127.0.0.1:5051/account")
            expect(page.get_by_text("Welcome, Synthetic Alex.", exact=True)).to_be_visible()
            assert db.users.count_documents({"identity_subject": user["identity_subject"]}) == 1
            report.update(
                registration=True,
                reserved_email_validation=True,
                profile_persisted=True,
                first_case=True,
                other_student_denied=True,
                admin_denied=True,
                repeat_login=True,
            )
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        with provider_session(values) as http:
            base = ORIGIN + "/admin/realms/student-support/users"
            response = http.get(base, params={"username": username, "exact": "true"}, timeout=5)
            response.raise_for_status()
            for provider in response.json():
                users = list(
                    db.users.find(
                        {
                            "identity_subject": provider["id"],
                            "identity_issuer": values["OIDC_ISSUER"],
                        },
                        {"_id": 1},
                    )
                )
                ids = [u["_id"] for u in users]
                cases = [c["_id"] for c in db.cases.find({"student_id": {"$in": ids}}, {"_id": 1})]
                for name in ["messages", "internal_notes", "case_events", "notification_outbox"]:
                    db[name].delete_many({"case_id": {"$in": cases}})
                db.submission_keys.delete_many({"user_id": {"$in": ids}})
                db.sessions.delete_many({"user_id": {"$in": ids}})
                db.audit_events.delete_many({"actor_id": {"$in": ids}})
                db.cases.delete_many({"_id": {"$in": cases}})
                db.users.delete_many({"_id": {"$in": ids}})
                response = http.delete(base + "/" + provider["id"], timeout=5)
                response.raise_for_status()
        web.close()
        maintenance.close()
        (evidence / f"{engine}-{width}-results.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
