"""Canonical host portals: one browser, distinct users, no account-reset workaround."""

import json
import os
import re
from pathlib import Path
from threading import Thread

import pytest
from dotenv import dotenv_values
from flask import g
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from app.portals import create_portals
from app.repositories.fixtures import fixture_id
from scripts.database_setup import local_client
from scripts.run_local import SafeRequestHandler

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = Path(os.getenv("PORTAL_EVIDENCE_DIR", str(ROOT / "docs/evidence/portal-redesign")))
pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(os.getenv("RUN_BROWSER") != "1", reason="Explicit isolated browsers"),
]


@pytest.fixture
def portals():
    values = dict(dotenv_values(ROOT / ".env"))
    gateway = create_portals(
        {
            **values,
            "APP_ENV": "testing",
            "MONGODB_DATABASE": "student_support_test",
            "APP_BASE_URL": "http://127.0.0.1:5051",
            "STUDENT_OIDC_CLIENT_ID": "support-student-test",
            "STAFF_OIDC_CLIENT_ID": "support-staff-test",
        }
    )
    web = local_client(values, "web_testing")
    maint = local_client(values, "testing")
    db = maint.student_support_test
    request_ids = []
    cases = []
    originals = {
        row["_id"]: row["display_name"]
        for row in db.users.find({"fixture_version": "synthetic-v1"}, {"display_name": 1})
    }
    team_names = {
        row["_id"]: row["name"]
        for row in db.teams.find({"fixture_version": "synthetic-v1"}, {"name": 1})
    }
    for key, label in team_names.items():
        db.teams.update_one({"_id": key}, {"$set": {"name": label.replace(" (synthetic)", "")}})
    for key, label in originals.items():
        clean = label.replace(" (synthetic)", "")
        if key == fixture_id("student_a"):
            clean = "Jordan Lee"
        if key == fixture_id("manager_finance"):
            clean = "Alex Morgan"
        db.users.update_one({"_id": key}, {"$set": {"display_name": clean}})
    for app in gateway.apps.values():
        app.extensions["mongo"].close()
        app.extensions["mongo"] = web

        @app.after_request
        def track(response):
            request_ids.append(g.request_id)
            return response

    server = make_server(
        "127.0.0.1", 5051, gateway, request_handler=SafeRequestHandler, threaded=True
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    try:
        yield gateway, db, cases
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        for collection in [
            "messages",
            "internal_notes",
            "case_events",
            "notification_outbox",
            "triage_claims",
        ]:
            db[collection].delete_many({"case_id": {"$in": cases}})
        db.submission_keys.delete_many({"result_id": {"$in": cases}})
        db.cases.delete_many({"_id": {"$in": cases}})
        db.audit_events.delete_many({"request_id": {"$in": request_ids}})
        for key, label in originals.items():
            db.users.update_one({"_id": key}, {"$set": {"display_name": label}})
        for key, label in team_names.items():
            db.teams.update_one({"_id": key}, {"$set": {"name": label}})
        web.close()
        maint.close()


def portal_login(page, origin, actor, capture):
    login = json.loads((ROOT / "runtime/synthetic-logins.json").read_text())[actor]
    page.goto(origin + "/sign-in")
    capture(page, "student-sign-in" if actor == "student_a" else "staff-sign-in")
    page.locator("#email").fill(login["username"] + "@example.invalid")
    page.get_by_role("button", name="Continue", exact=True).click()
    page.get_by_role("link", name="Continue to secure sign-in", exact=True).click()
    # The supplied email must select the intended identity without "Not you?".
    expect(page.locator("#username")).to_be_editable()
    expect(page.locator("#username")).to_have_value(login["username"] + "@example.invalid")
    page.locator("#password").fill(login["password"])
    page.locator("#kc-login").click()
    if page.locator("#input-error").count():
        assert not page.locator("#input-error").is_visible(), page.locator("body").inner_text()
    try:
        page.wait_for_url(origin + "/account", timeout=10000)
    except Exception as error:
        raise AssertionError(page.locator("body").inner_text()) from error


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
@pytest.mark.parametrize("width", [390, 768, 1440])
@pytest.mark.parametrize("first", ["student", "staff"])
def test_real_portal_signin_case_reply_isolation_and_design(portals, engine, width, first):
    _, db, cases = portals
    student_origin = "http://127.0.0.1:5051"
    staff_origin = "http://localhost:5051"
    with sync_playwright() as pw:
        browser = getattr(pw, engine).launch()
        context = browser.new_context(viewport={"width": width, "height": 1000})
        student = context.new_page()
        staff = context.new_page()

        def capture(page, name):
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not re.search(
                r"\b(demo|synthetic|fictional)\b", page.locator("body").inner_text(), re.I
            )
            page.evaluate(
                (ROOT / "runtime/accessibility/node_modules/axe-core/axe.min.js").read_text()
            )
            result = page.evaluate(
                "async()=>await axe.run(document,{runOnly:{type:'tag',"
                "values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}})"
            )
            violations = [(v["id"], v["impact"]) for v in result["violations"]]
            (EVIDENCE / f"{engine}-{width}-{name}-axe.json").write_text(
                json.dumps({"screen": name, "violations": result["violations"]}, indent=2) + "\n"
            )
            assert not violations, violations
            page.screenshot(path=str(EVIDENCE / f"{engine}-{width}-{name}.png"), full_page=True)

        try:
            student.goto(student_origin)
            capture(student, "home")
            student.goto(student_origin + "/support")
            capture(student, "services")
            if first == "staff":
                portal_login(staff, staff_origin, "manager_finance", capture)
                portal_login(student, student_origin, "student_a", capture)
            else:
                portal_login(student, student_origin, "student_a", capture)
                portal_login(staff, staff_origin, "manager_finance", capture)
            capture(student, "student-dashboard")
            capture(staff, "staff-dashboard")
            student.reload()
            expect(student.get_by_text("Welcome, Jordan Lee.", exact=True)).to_be_visible()
            staff.reload()
            expect(staff.get_by_text("Welcome, Alex Morgan.", exact=True)).to_be_visible()
            cookies = context.cookies()
            assert (
                next(c for c in cookies if c["name"] == "support_session_student")["domain"]
                == "127.0.0.1"
            )
            assert (
                next(c for c in cookies if c["name"] == "support_session_university")["domain"]
                == "localhost"
            )
            student.goto(student_origin + "/cases/new")
            student.locator("#category").select_option("finance")
            student.locator("#description").fill(
                "I would like help understanding my living costs this term."
            )
            student.get_by_role("button", name="Send support request", exact=True).click()
            student.wait_for_url(re.compile("/cases/[0-9a-f-]+\\?submitted=1"))
            case = student.url.split("/cases/")[1].split("?")[0]
            cases.append(case)
            staff_url = staff_origin + "/staff/cases/" + case
            staff.goto(staff_url)
            staff.locator("#operation").select_option("assign")
            staff.locator("#assignee").select_option(fixture_id("manager_finance"))
            staff.locator("#reason").fill("Allocate to the finance support team.")
            staff.get_by_role("button", name="Confirm action", exact=True).click()
            staff.wait_for_url(staff_origin + "/staff")
            staff.goto(staff_url)
            staff.locator("#reason").fill("Review the student request.")
            staff.get_by_role("button", name="Confirm action", exact=True).click()
            staff.wait_for_url(staff_origin + "/staff")
            staff.goto(staff_url)
            staff.locator("#body").fill(
                "Thank you for getting in touch. Could you tell us which costs are causing concern?"
            )
            staff.get_by_role("button", name="Confirm conversation action").click()
            staff.wait_for_url(staff_url)
            capture(staff, "case-work")
            student.reload()
            expect(
                student.get_by_text(
                    "Thank you for getting in touch. Could you tell us which costs are causing concern?",
                    exact=True,
                )
            ).to_be_visible()
            capture(student, "student-conversation")
            student.goto(student_origin + "/account")
            student.get_by_role("button", name="Sign out of Student Support", exact=True).click()
            staff.goto(staff_origin + "/account")
            expect(staff.get_by_text("Welcome, Alex Morgan.", exact=True)).to_be_visible()

        finally:
            context.close()
            browser.close()


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
def test_admin_login_from_old_staff_bookmark_with_remembered_student(portals, engine):
    with sync_playwright() as pw:
        browser = getattr(pw, engine).launch()
        context = browser.new_context()
        student = context.new_page()
        admin = context.new_page()
        try:
            portal_login(student, "http://127.0.0.1:5051", "student_a", lambda *args: None)
            admin.goto("http://127.0.0.1:5051/staff/sign-in")
            expect(admin).to_have_url("http://localhost:5051/staff/sign-in")
            admin.get_by_role("link", name="Sign in as university staff").click()
            expect(admin).to_have_url("http://localhost:5051/sign-in")
            portal_login(admin, "http://localhost:5051", "administrator", lambda *args: None)
            admin.goto("http://localhost:5051/access/invitations")
            expect(
                admin.get_by_role("heading", name="University invitations", exact=True)
            ).to_be_visible()
            student.reload()
            expect(student.get_by_text("Welcome, Jordan Lee.", exact=True)).to_be_visible()
            admin.goto("http://localhost:5051/account")
            admin.get_by_role("button", name="Sign out of Student Support", exact=True).click()
            student.reload()
            expect(student.get_by_text("Welcome, Jordan Lee.", exact=True)).to_be_visible()
        finally:
            context.close()
            browser.close()
