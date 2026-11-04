"""Regression: two tabs sharing one cookie jar must retain distinct principals."""

import json
import os
import re
from pathlib import Path
from threading import Thread
from uuid import uuid4

import pytest
from dotenv import dotenv_values
from flask import g
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from app import create_app
from app.repositories.fixtures import fixture_id
from scripts.database_setup import local_client
from scripts.run_local import SafeRequestHandler

ROOT = Path(__file__).resolve().parents[2]
pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(os.getenv("RUN_BROWSER") != "1", reason="Isolated real browser regression"),
]


@pytest.fixture
def parallel_app():
    values = dict(dotenv_values(ROOT / ".env"))
    app = create_app(
        {
            **values,
            "APP_ENV": "testing",
            "MONGODB_DATABASE": "student_support_test",
            "APP_BASE_URL": "http://127.0.0.1:5051",
            "OIDC_CLIENT_ID": "support-test",
        }
    )
    app.extensions["mongo"].close()
    web = local_client(values, "web_testing")
    maint = local_client(values, "testing")
    app.extensions["mongo"] = web
    request_ids = []

    @app.after_request
    def track(response):
        request_ids.append(g.request_id)
        return response

    server = make_server("127.0.0.1", 5051, app, request_handler=SafeRequestHandler, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    cases = []
    try:
        yield maint.student_support_test, cases
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        db = maint.student_support_test
        for name in [
            "messages",
            "internal_notes",
            "case_events",
            "notification_outbox",
            "triage_claims",
        ]:
            db[name].delete_many({"case_id": {"$in": cases}})
        db.submission_keys.delete_many({"result_id": {"$in": cases}})
        db.audit_events.delete_many({"request_id": {"$in": request_ids}})
        db.cases.delete_many({"_id": {"$in": cases}})
        web.close()
        maint.close()


def login(page, prefix, actor):
    credentials = json.loads((ROOT / "runtime/synthetic-logins.json").read_text())[actor]
    page.goto("http://127.0.0.1:5051" + prefix + "/sign-in")
    assert "prompt=login" in page.url
    if page.locator("#reset-login").count():
        page.locator("#reset-login").click()
    page.locator("#username").fill(credentials["username"])
    page.locator("#password").fill(credentials["password"])
    page.locator("#kc-login").click()
    page.wait_for_url("http://127.0.0.1:5051" + prefix + "/account")


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
@pytest.mark.parametrize("first", ["student", "staff"])
def test_two_tabs_one_browser_independent_accounts_request_reply_and_logout(
    parallel_app, engine, first
):
    db, cases = parallel_app
    folder = ROOT / "docs/evidence/parallel-accounts"
    folder.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        browser = getattr(pw, engine).launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        student, staff = context.new_page(), context.new_page()
        actors = {
            "student": (student, "/student", "student_a"),
            "staff": (staff, "/university", "manager_finance"),
        }
        try:
            for actor in [first, "staff" if first == "student" else "student"]:
                login(*actors[actor])
            student.reload()
            staff.reload()
            expect(
                student.get_by_text("Welcome, Student A (synthetic).", exact=True)
            ).to_be_visible()
            expect(
                staff.get_by_text("Welcome, Manager Finance (synthetic).", exact=True)
            ).to_be_visible()
            cookies = context.cookies()
            assert {
                c["name"]: c["path"] for c in cookies if c["name"].startswith("support_session")
            } == {
                "support_session_student": "/student",
                "support_session_university": "/university",
            }
            student.goto("http://127.0.0.1:5051/student/cases/new")
            student.locator("#category").select_option("finance")
            student.locator("#description").fill("Synthetic same-browser request " + uuid4().hex)
            student.get_by_role("button", name="Send support request", exact=True).click()
            student.wait_for_url(re.compile("/student/cases/[0-9a-f-]+\\?submitted=1"))
            case = student.url.split("/cases/")[1].split("?")[0]
            cases.append(case)
            staff_url = "http://127.0.0.1:5051/university/staff/cases/" + case
            staff.goto(staff_url)
            staff.locator("#operation").select_option("assign")
            staff.locator("#assignee").select_option(fixture_id("manager_finance"))
            staff.locator("#reason").fill("Synthetic manager allocation")
            staff.get_by_role("button", name="Confirm action", exact=True).click()
            staff.wait_for_url("http://127.0.0.1:5051/university/staff")
            staff.goto(staff_url)
            staff.locator("#reason").fill("Start synthetic support")
            staff.get_by_role("button", name="Confirm action", exact=True).click()
            staff.wait_for_url("http://127.0.0.1:5051/university/staff")
            staff.goto(staff_url)
            staff.locator("#body").fill("Staff reply from the other tab")
            staff.get_by_role("button", name="Confirm conversation action").click()
            staff.wait_for_url(staff_url)
            student.reload()
            expect(
                student.get_by_text("Staff reply from the other tab", exact=True)
            ).to_be_visible()
            assert db.cases.find_one({"_id": case})["student_id"] == fixture_id("student_a")
            student.screenshot(path=str(folder / f"{engine}-{first}-student.png"), full_page=True)
            staff.screenshot(path=str(folder / f"{engine}-{first}-staff.png"), full_page=True)
            # CSRF from one workspace cannot authorise a mutation in the other.
            student_csrf = student.locator("[name=csrf_token]").first.input_value()
            response = staff.request.post(
                "http://127.0.0.1:5051/university/sign-out", form={"csrf_token": student_csrf}
            )
            assert response.status == 400
            student.goto("http://127.0.0.1:5051/student/account")
            student.get_by_role("button", name="Sign out of Student Support").click()
            staff.goto("http://127.0.0.1:5051/university/account")
            expect(
                staff.get_by_text("Welcome, Manager Finance (synthetic).", exact=True)
            ).to_be_visible()
            assert not any(c["name"] == "support_session_student" for c in context.cookies())
            assert any(c["name"] == "support_session_university" for c in context.cookies())
        finally:
            context.close()
            browser.close()


@pytest.mark.parametrize("student_engine", ["chromium", "webkit"])
def test_different_browsers_keep_legacy_accounts_independent(parallel_app, student_engine):
    with sync_playwright() as pw:
        other = "webkit" if student_engine == "chromium" else "chromium"
        student_browser = getattr(pw, student_engine).launch()
        staff_browser = getattr(pw, other).launch()
        try:
            student = student_browser.new_page()
            staff = staff_browser.new_page()
            login(student, "", "student_a")
            login(staff, "", "manager_finance")
            student.reload()
            staff.reload()
            expect(
                student.get_by_text("Welcome, Student A (synthetic).", exact=True)
            ).to_be_visible()
            expect(
                staff.get_by_text("Welcome, Manager Finance (synthetic).", exact=True)
            ).to_be_visible()
        finally:
            student_browser.close()
            staff_browser.close()
