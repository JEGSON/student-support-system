"""Real OIDC student/staff lifecycle, referral isolation and WCAG automation."""

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
    pytest.mark.skipif(os.getenv("RUN_BROWSER") != "1", reason="Explicit local browser suite"),
]
ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/evidence/stage-14"


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
@pytest.mark.parametrize("width", [390, 768, 1440])
def test_complete_case_lifecycle(engine, width):
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
    maint = local_client(values, "testing")
    db = maint.student_support_test
    app.extensions["mongo"] = web
    accounts = json.loads((ROOT / "runtime/synthetic-logins.json").read_text())
    marker = "Synthetic complete flow " + uuid4().hex
    private = "PRIVATE_NOTE_" + uuid4().hex
    request_ids = []
    case_ids = []
    contexts = []
    reports = {}
    server = make_server("127.0.0.1", 5051, app, request_handler=SafeRequestHandler, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    axe = ROOT / "runtime/accessibility/node_modules/axe-core/axe.min.js"
    assert axe.exists(), "Install the documented development-only axe-core dependency."

    def login(browser, name):
        context = browser.new_context(
            viewport={"width": width, "height": 1000},
            locale="en-GB",
            timezone_id="Europe/London",
            reduced_motion="reduce",
        )
        contexts.append(context)
        page = context.new_page()
        page.on("response", lambda r: request_ids.append(r.headers.get("x-request-id", "")))
        if name == "student_a":
            page.goto("http://127.0.0.1:5051/sign-in")
        else:
            page.goto("http://127.0.0.1:5051/")
            page.get_by_role("link", name="University staff sign-in", exact=True).click()
            page.get_by_role("link", name="Sign in as university staff", exact=True).click()
        page.locator("#username").fill(accounts[name]["username"])
        page.locator("#password").fill(accounts[name]["password"])
        page.locator("#kc-login").click()
        page.wait_for_url("http://127.0.0.1:5051/account")
        return page

    def review(page, name):
        expect(page.locator("h1")).to_be_visible()
        assert page.locator("h1").count() == 1
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.evaluate(axe.read_text())
        result = page.evaluate(
            "async()=>await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}})"
        )
        reports[name] = {
            "violations": result["violations"],
            "incomplete": [{"id": r["id"]} for r in result["incomplete"]],
            "passes": len(result["passes"]),
        }
        assert not result["violations"], [(v["id"], v["impact"]) for v in result["violations"]]
        page.screenshot(path=str(EVIDENCE / f"{engine}-{width}-{name}.png"), full_page=True)

    try:
        with sync_playwright() as pw:
            browser = getattr(pw, engine).launch()
            student = login(browser, "student_a")
            student.goto("http://127.0.0.1:5051/cases/new")
            student.locator("#category").select_option("finance")
            student.locator("#description").focus()
            student.keyboard.type(marker + "\n" + "Synthetic long description. " * 40)
            student.get_by_role("button", name="Send support request", exact=True).click()
            student.wait_for_url(re.compile("/cases/[0-9a-f-]+\\?submitted=1"))
            case_id = student.url.split("/cases/")[1].split("?")[0]
            case_ids.append(case_id)
            case_url = "http://127.0.0.1:5051/staff/cases/" + case_id
            manager = login(browser, "manager_finance")
            manager.goto("http://127.0.0.1:5051/staff")
            review(manager, "staff-queue")
            manager.goto(case_url)
            manager.locator("#operation").select_option("assign")
            manager.locator("#assignee").select_option(fixture_id("officer_assigned"))
            manager.locator("#reason").fill("Synthetic allocation")
            manager.get_by_role("button", name="Confirm action", exact=True).click()
            manager.wait_for_url("http://127.0.0.1:5051/staff")
            officer = login(browser, "officer_assigned")
            officer.goto(case_url)
            officer.locator("#operation").select_option("start")
            officer.locator("#reason").fill("Begin support")
            officer.get_by_role("button", name="Confirm action", exact=True).click()
            officer.wait_for_url("http://127.0.0.1:5051/staff")
            officer.goto(case_url)
            officer.locator("#communication-action").select_option("question")
            officer.locator("#body").fill("Synthetic question for the student")
            officer.get_by_role("button", name="Confirm conversation action").click()
            officer.wait_for_url(case_url)
            officer.locator("#note").fill(private)
            officer.get_by_role("button", name="Record internal note").click()
            officer.wait_for_url(case_url)
            review(officer, "staff-notes")
            student.goto("http://127.0.0.1:5051/cases/" + case_id)
            assert private not in student.content()
            student.locator("#body").fill("Synthetic student reply")
            student.get_by_role("button", name="Send message", exact=True).click()
            student.wait_for_url("http://127.0.0.1:5051/cases/" + case_id)
            review(student, "student-conversation")
            officer.goto(case_url)
            officer.locator("#target").select_option(fixture_id("team_disability"))
            officer.locator("#referral-category").select_option("disability")
            officer.locator("#purpose").fill("Synthetic selected handover")
            officer.locator("#summary").fill("Minimal synthetic summary only")
            officer.get_by_role("button", name="Propose for manager approval").click()
            officer.wait_for_url("http://127.0.0.1:5051/staff/referrals")
            manager.goto("http://127.0.0.1:5051/staff/referrals")
            manager.locator("select[name=decision]").select_option("approve")
            manager.locator("textarea[name=reason]").fill("Reviewed sharing")
            manager.get_by_role("button", name="Record decision").click()
            manager.wait_for_url("http://127.0.0.1:5051/staff/referrals")
            target = login(browser, "manager_disability")
            target.goto("http://127.0.0.1:5051/staff/referrals")
            assert marker not in target.content() and private not in target.content()
            review(target, "minimal-referral")
            target.locator("select[name=decision]").select_option("accept")
            target.locator("textarea[name=reason]").fill("Target accepts summary")
            target.get_by_role("button", name="Record decision").click()
            target.wait_for_url("http://127.0.0.1:5051/staff/referrals")
            newcase = db.referrals.find_one({"source_case_id": case_id})["target_case_id"]
            case_ids.append(newcase)
            officer.goto(case_url)
            officer.locator("#communication-action").select_option("close")
            officer.locator("#body").fill("Synthetic resolution recorded")
            officer.get_by_role("button", name="Confirm conversation action").click()
            officer.wait_for_url(case_url)
            student.goto("http://127.0.0.1:5051/cases/" + case_id)
            expect(student.get_by_text("Closed", exact=True)).to_be_visible()
            assert private not in student.content()
            review(student, "closed-outcome")
            # Real stale-version form is rejected and does not overwrite a newer action.
            stale = manager.request.post(
                "http://127.0.0.1:5051/staff/cases/" + case_id + "/action",
                form={
                    "csrf_token": manager.locator("[name=csrf_token]").first.input_value(),
                    "operation": "assign",
                    "version": "1",
                    "assignee": fixture_id("officer_assigned"),
                    "reason": "Stale action",
                },
            )
            assert stale.status == 409
            student.goto("http://127.0.0.1:5051/cases/" + newcase)
            student.locator("#body").fill("Synthetic expired unsaved draft")
            student.context.clear_cookies()
            student.get_by_role("button", name="Send message", exact=True).click()
            expect(student.get_by_role("heading", name="Your form has expired")).to_be_visible()
            assert "Synthetic expired unsaved draft" not in student.content()
            review(student, "session-expired")
            for context in contexts:
                context.close()
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        for row in db.cases.find(
            {
                "student_id": fixture_id("student_a"),
                "description": {"$regex": "^" + re.escape(marker)},
            },
            {"_id": 1},
        ):
            if row["_id"] not in case_ids:
                case_ids.append(row["_id"])
        referral_ids = [
            r["_id"] for r in db.referrals.find({"source_case_id": {"$in": case_ids}}, {"_id": 1})
        ]
        for row in db.cases.find({"originating_referral_id": {"$in": referral_ids}}, {"_id": 1}):
            if row["_id"] not in case_ids:
                case_ids.append(row["_id"])
        mids = [r["_id"] for r in db.messages.find({"case_id": {"$in": case_ids}}, {"_id": 1})]
        for name in [
            "messages",
            "internal_notes",
            "case_events",
            "notification_outbox",
            "triage_claims",
        ]:
            db[name].delete_many({"case_id": {"$in": case_ids}})
        db.referrals.delete_many({"source_case_id": {"$in": case_ids}})
        db.submission_keys.delete_many({"result_id": {"$in": [*case_ids, *mids]}})
        db.cases.delete_many({"_id": {"$in": case_ids}})
        db.audit_events.delete_many(
            {"$or": [{"target_id": {"$in": case_ids}}, {"request_id": {"$in": request_ids}}]}
        )
        (EVIDENCE / f"{engine}-{width}-axe.json").write_text(json.dumps(reports, indent=2))
        web.close()
        maint.close()


@pytest.mark.parametrize("engine", ["chromium", "webkit"])
def test_keyboard_and_large_text_reflow(engine, config):
    application = create_app(config)
    server = make_server(
        "127.0.0.1", 0, application, request_handler=SafeRequestHandler, threaded=True
    )
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as pw:
            browser = getattr(pw, engine).launch()
            page = browser.new_page(viewport={"width": 640, "height": 1000})
            page.goto("http://127.0.0.1:" + str(server.server_port))
            page.keyboard.press("Alt+Tab" if engine == "webkit" else "Tab")
            assert page.evaluate("document.activeElement.classList.contains('skip')")
            page.keyboard.press("Enter")
            page.keyboard.press("Alt+Tab" if engine == "webkit" else "Tab")
            assert page.evaluate("document.activeElement.tagName !== 'BODY'")
            page.evaluate("document.documentElement.style.fontSize='200%'")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(EVIDENCE / f"{engine}-large-text.png"), full_page=True)
            browser.close()
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        application.extensions["mongo"].close()
