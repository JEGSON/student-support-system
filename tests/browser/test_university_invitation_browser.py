"""Real operator/team/invitation UI and verified provider staff enrolment."""

import json
import os
import secrets
from pathlib import Path
from threading import Thread
from uuid import uuid4

import pytest
from dotenv import dotenv_values
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from app import create_app
from scripts.configure_registration import ORIGIN, provider_session
from scripts.database_setup import local_client
from scripts.run_local import SafeRequestHandler

ROOT = Path(__file__).resolve().parents[2]
pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(os.getenv("RUN_BROWSER") != "1", reason="Explicit isolated browsers"),
]


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
@pytest.mark.parametrize("width", [390, 1440])
def test_administrator_team_invitation_and_verified_staff_signin(engine, width):
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
    server = make_server("127.0.0.1", 5051, app, threaded=True, request_handler=SafeRequestHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    accounts = json.loads((ROOT / "runtime/synthetic-logins.json").read_text())
    username = "invited_" + uuid4().hex
    email = username + "@example.invalid"
    password = "Staff9" + secrets.token_urlsafe(24)
    team_name = "University onboarding " + uuid4().hex
    provider_id = None
    team_id = None
    request_ids = []
    folder = ROOT / "docs/evidence/real-service"
    folder.mkdir(parents=True, exist_ok=True)
    try:
        with provider_session(values) as http:
            base = ORIGIN + "/admin/realms/student-support/users"
            response = http.post(
                base,
                json={
                    "username": username,
                    "enabled": True,
                    "firstName": "Verified",
                    "lastName": "Staff",
                    "email": email,
                    "emailVerified": True,
                    "credentials": [{"type": "password", "value": password, "temporary": False}],
                },
                timeout=5,
            )
            response.raise_for_status()
            response = http.get(base, params={"username": username, "exact": "true"}, timeout=5)
            response.raise_for_status()
            provider_id = response.json()[0]["id"]
        with sync_playwright() as pw:
            browser = getattr(pw, engine).launch()
            admin = browser.new_page(viewport={"width": width, "height": 1000})
            admin.on("response", lambda r: request_ids.append(r.headers.get("x-request-id", "")))
            admin.goto("http://127.0.0.1:5051/sign-in")
            admin.locator("#username").fill(accounts["administrator"]["username"])
            admin.locator("#password").fill(accounts["administrator"]["password"])
            admin.locator("#kc-login").click()
            admin.wait_for_url("http://127.0.0.1:5051/account")
            admin.goto("http://127.0.0.1:5051/access/teams")
            admin.locator("#name-new").fill(team_name)
            admin.locator("#category-new-finance").check()
            admin.locator("#routing-new-finance").check()
            admin.get_by_role("button", name="Create team", exact=True).click()
            admin.wait_for_url("http://127.0.0.1:5051/access/teams")
            team_id = db.teams.find_one({"name": team_name})["_id"]
            assert admin.evaluate("document.documentElement.scrollWidth <= innerWidth")
            admin.goto("http://127.0.0.1:5051/access/invitations")
            admin.locator("#email").fill(email)
            admin.locator("#role").select_option("officer")
            admin.locator("#team").select_option(team_id)
            admin.get_by_role("button", name="Create invitation", exact=True).click()
            expect(
                admin.get_by_role("heading", name="Invitation created", exact=True)
            ).to_be_visible()
            code = admin.locator(".alert code").inner_text()
            assert db.enrolment_invitations.find_one({"email": email})["state"] == "pending"
            # Navigate away from the one-time secret before saving any screenshot.
            admin.goto("http://127.0.0.1:5051/access/invitations")
            assert admin.locator(".alert code").count() == 0
            assert admin.evaluate("document.documentElement.scrollWidth <= innerWidth")
            axe = (ROOT / "runtime/accessibility/node_modules/axe-core/axe.min.js").read_text()
            admin.evaluate(axe)
            result = admin.evaluate(
                "async()=>await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}})"
            )
            assert not result["violations"], [(v["id"], v["impact"]) for v in result["violations"]]
            admin.screenshot(path=str(folder / f"{engine}-{width}-invitations.png"), full_page=True)
            context = browser.new_context(viewport={"width": width, "height": 1000})
            staff = context.new_page()
            staff.on("response", lambda r: request_ids.append(r.headers.get("x-request-id", "")))
            staff.goto("http://127.0.0.1:5051/join")
            staff.locator("#code").fill(code)
            staff.get_by_role("button", name="Continue with invitation", exact=True).click()
            staff.wait_for_url("http://127.0.0.1:5051/join/continue")
            staff.get_by_role("link", name="Continue with university account").click()
            staff.locator("#username").fill(username)
            staff.locator("#password").fill(password)
            staff.locator("#kc-login").click()
            staff.wait_for_url("http://127.0.0.1:5051/account")
            staff.get_by_role("link", name="Open staff workspace", exact=True).click()
            expect(
                staff.get_by_role("heading", name="A clear view of your team's work.")
            ).to_be_visible()
            user = db.users.find_one({"identity_subject": provider_id})
            assert user["global_roles"] == []
            assert db.memberships.find_one(
                {"user_id": user["_id"], "team_id": team_id, "role": "officer", "active": True}
            )
            assert staff.request.get("http://127.0.0.1:5051/access").status == 403
            assert db.enrolment_invitations.find_one({"email": email})["state"] == "accepted"
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        if provider_id:
            ids = [u["_id"] for u in db.users.find({"identity_subject": provider_id}, {"_id": 1})]
            db.memberships.delete_many({"user_id": {"$in": ids}})
            db.sessions.delete_many({"user_id": {"$in": ids}})
            db.audit_events.delete_many({"actor_id": {"$in": ids}})
            db.users.delete_many({"_id": {"$in": ids}})
            with provider_session(values) as http:
                http.delete(
                    ORIGIN + "/admin/realms/student-support/users/" + provider_id, timeout=5
                ).raise_for_status()
        if team_id:
            db.audit_events.delete_many({"target_type": "team", "target_id": team_id})
            db.teams.delete_one({"_id": team_id})
        db.enrolment_invitations.delete_many({"email": email})
        db.audit_events.delete_many({"request_id": {"$in": request_ids}})
        web.close()
        maintenance.close()
