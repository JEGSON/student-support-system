"""Stage 08 HTTP/service acceptance and negative security checks on real MongoDB."""

import json
import os
import re
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import dotenv_values

from app import create_app
from app.auth.sessions import COOKIE, token_hash
from app.repositories.core import utc_now
from app.services.audit import AuditWriter
from app.services.outbox import Outbox
from app.services.student_cases import StudentCases
from scripts.database_setup import local_client

pytestmark = [
    pytest.mark.runtime,
    pytest.mark.skipif(os.getenv("RUN_RUNTIME") != "1", reason="Isolated MongoDB required"),
]


@pytest.fixture
def student_app(bundle, config):
    db, uid = bundle
    values = dotenv_values(Path(__file__).resolve().parents[2] / ".env")
    web = local_client(values, "web_testing")
    routing = {
        name: uid("team_" + name)
        for name in ["academic", "finance", "wellbeing", "disability", "accommodation"]
    }
    app = create_app({**config, "CASE_ROUTING_JSON": json.dumps(routing)})
    app.extensions["mongo"].close()
    app.extensions["mongo"] = web

    def browser(actor="student_a", context="student"):
        raw = secrets.token_urlsafe(32)
        now = utc_now()
        db.sessions.insert_one(
            {
                "_id": str(uuid4()),
                "token_hash": token_hash(raw),
                "user_id": uid(actor),
                "created_at": now,
                "last_seen_at": now,
                "idle_expires_at": now + timedelta(minutes=30),
                "absolute_expires_at": now + timedelta(hours=8),
                "authentication_time": now,
                "data": {"context": context},
                "version": 0,
                "fixture_version": "synthetic-v1",
            }
        )
        client = app.test_client()
        client.set_cookie(COOKIE, raw)
        return client

    yield app, browser, routing
    web.close()


def form(client):
    response = client.get("/cases/new")
    assert response.status_code == 200
    fields = {
        name: re.search(rf'name="{name}" value="([^"]+)"'.encode(), response.data)[1].decode()
        for name in ["csrf_token", "submission_key"]
    }
    return {**fields, "category": "finance", "description": "Synthetic support with living costs."}


def test_complete_submit_list_detail_and_lost_response_replay(bundle, student_app):
    db, uid = bundle
    app, browser, _ = student_app
    client = browser()
    data = form(client)
    response = client.post(
        "/cases/new", data=data, headers={"X-Request-ID": "untrusted-sensitive-value"}
    )
    assert response.status_code == 303 and "description" not in response.location
    case_id = response.location.split("/")[-1].split("?")[0]
    case = db.cases.find_one({"_id": case_id})
    assert (
        case["student_id"] == uid("student_a")
        and case["assignee_id"] is None
        and case["status"] == "New"
        and case["version"] == 1
    )
    assert case["team_id"] == uid("team_finance") and case["created_at"] == case["updated_at"]
    assert len(case["reference"]) <= 40 and case["reference"].startswith("SS-")
    assert "untrusted" not in response.headers["X-Request-ID"]
    audit = db.audit_events.find_one({"target_id": case_id, "action": "case_submitted"})
    assert audit["request_id"] == response.headers["X-Request-ID"]
    replay = client.post("/cases/new", data=data)
    assert replay.status_code == 303 and replay.location == response.location
    for collection in ["case_events", "notification_outbox"]:
        assert db[collection].count_documents({"case_id": case_id}) == 1
    assert db.audit_events.count_documents({"target_id": case_id, "action": "case_submitted"}) == 1
    page = client.get(response.location)
    assert (
        page.status_code == 200
        and case["reference"].encode() in page.data
        and b"Your request is recorded" in page.data
    )
    assert "no-store" in page.headers["Cache-Control"] and data["description"].encode() in page.data
    overview = client.get("/cases")
    assert overview.status_code == 200 and case["reference"].encode() in overview.data
    assert b"SS-DEMO-CASE_B" not in overview.data
    assert (
        client.post(
            "/cases/new", data={**data, "description": "Different synthetic request"}
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("student_id", "forged"),
        ("owner_id", "forged"),
        ("status", "Closed"),
        ("team_id", "forged"),
        ("priority", "urgent"),
        ("global_roles", "administrator"),
    ],
)
def test_server_owned_fields_rejected(bundle, student_app, field, value):
    db, uid = bundle
    _, browser, _ = student_app
    client = browser()
    data = form(client)
    before = db.cases.count_documents({"student_id": uid("student_a")})
    assert client.post("/cases/new", data={**data, field: value}).status_code == 400
    assert db.cases.count_documents({"student_id": uid("student_a")}) == before


@pytest.mark.parametrize(
    "category,description,field",
    [
        ("other", "Synthetic request", "category"),
        ("finance", "   ", "description"),
        ("finance", "x" * 10001, "description"),
        ("finance", "a\x00b", "description"),
    ],
)
def test_validation_usable_and_inert(student_app, category, description, field):
    _, browser, _ = student_app
    client = browser()
    data = form(client)
    response = client.post(
        "/cases/new", data={**data, "category": category, "description": description}
    )
    assert response.status_code == 422 and b"Check your request" in response.data
    assert (
        f'id="{field}-error"'.encode() in response.data and b'aria-invalid="true"' in response.data
    )
    assert data["submission_key"].encode() in response.data


def test_csrf_duplicate_fields_json_and_foreign_form_key_denied(student_app):
    _, browser, _ = student_app
    client = browser()
    data = form(client)
    assert (
        client.post(
            "/cases/new", data={k: v for k, v in data.items() if k != "csrf_token"}
        ).status_code
        == 400
    )
    assert client.get("/cases/new", query_string={"description": "not-created"}).status_code == 200
    assert (
        client.post(
            "/cases/new",
            json={"category": {"$ne": None}, "description": "x"},
            headers={"X-CSRFToken": data["csrf_token"]},
        ).status_code
        == 400
    )
    from werkzeug.datastructures import MultiDict

    assert (
        client.post(
            "/cases/new", data=MultiDict([*data.items(), ("category", "academic")])
        ).status_code
        == 400
    )
    foreign = browser("student_b")
    foreign_data = form(foreign)
    assert (
        foreign.post(
            "/cases/new", data={**foreign_data, "submission_key": data["submission_key"]}
        ).status_code
        == 400
    )
    assert client.post("/cases/new", data={**data, "submission_key": "forged"}).status_code == 400


def test_cross_student_unknown_malformed_and_archived_case_have_same_denial(bundle, student_app):
    db, uid = bundle
    _, browser, _ = student_app
    client = browser()
    foreign = client.get("/cases/" + uid("case_b"))
    missing = client.get("/cases/" + str(uuid4()))
    bad = client.get("/cases/not-an-id")
    assert foreign.status_code == missing.status_code == bad.status_code == 404
    assert foreign.data == missing.data == bad.data
    assert b"SS-DEMO-CASE_B" not in foreign.data
    db.cases.update_one({"_id": uid("case_a")}, {"$set": {"archive_state": "archived"}})
    assert client.get("/cases/" + uid("case_a")).status_code == 404
    assert b"SS-DEMO-CASE_A<" not in client.get("/cases").data


def test_scripts_escape_and_staff_only_records_never_appear(bundle, student_app, caplog):
    db, uid = bundle
    _, browser, _ = student_app
    client = browser()
    data = form(client)
    script = "</textarea><script>window.syntheticExecuted=true</script><b>synthetic</b>"
    response = client.post("/cases/new", data={**data, "description": script})
    page = client.get(response.location)
    assert b"&lt;script&gt;" in page.data and b"<script>" not in page.data
    marker = "SYNTHETIC_INTERNAL_ONLY_NEVER_RETURN"
    db.internal_notes.update_one({"case_id": uid("case_a")}, {"$set": {"body": marker}})
    db.case_events.insert_one(
        {
            "_id": str(uuid4()),
            "case_id": uid("case_a"),
            "actor_id": uid("officer_assigned"),
            "event_type": "note_added",
            "reason": marker,
            "created_at": utc_now(),
        }
    )
    for path in ["/cases", "/cases/" + uid("case_a")]:
        page = client.get(path)
        assert page.status_code == 200 and marker.encode() not in page.data
        assert b"INTERNAL_NOTE" not in page.data
    assert marker not in caplog.text and script not in caplog.text
    assert script not in str(
        list(db.notification_outbox.find({"recipient_user_id": uid("student_a")}))
    )
    assert script not in str(list(db.audit_events.find({"actor_id": uid("student_a")})))
    assert script not in str(list(db.sessions.find({"user_id": uid("student_a")})))


@pytest.mark.parametrize("source", ["missing", "inactive"])
def test_missing_or_inactive_routing_no_partial_case_and_form_retry_preserved(
    bundle, student_app, source
):
    db, uid = bundle
    app, browser, _ = student_app
    client = browser()
    data = form(client)
    if source == "missing":
        app.config["CASE_ROUTING"] = {}
    else:
        db.teams.update_one({"_id": uid("team_finance")}, {"$set": {"active": False}})
    before = db.cases.count_documents({"student_id": uid("student_a")})
    response = client.post("/cases/new", data=data)
    assert (
        response.status_code == 503
        and data["description"].encode() in response.data
        and data["submission_key"].encode() in response.data
    )
    assert db.cases.count_documents({"student_id": uid("student_a")}) == before
    assert db.submission_keys.count_documents({"user_id": uid("student_a")}) == 0


@pytest.mark.parametrize("action", ["list", "detail"])
def test_audit_failure_returns_no_sensitive_content(bundle, student_app, monkeypatch, action):
    _, uid = bundle
    _, browser, _ = student_app
    client = browser()

    def unavailable(*args, **kwargs):
        from pymongo.errors import OperationFailure

        raise OperationFailure("Sensitive error text must not escape")

    monkeypatch.setattr(AuditWriter, "append", unavailable)
    response = client.get("/cases" if action == "list" else "/cases/" + uid("case_a"))
    assert (
        response.status_code == 503
        and b"SS-DEMO-" not in response.data
        and b"Sensitive error text" not in response.data
    )


def test_creation_rollback_and_same_key_concurrent_replay(bundle, student_app, monkeypatch):
    db, uid = bundle
    app, _, routing = student_app
    service = StudentCases(app.extensions["mongo"].student_support_test, routing)
    original = Outbox.enqueue

    def fail(*args, **kwargs):
        raise RuntimeError("Synthetic failure after case/event/audit")

    monkeypatch.setattr(Outbox, "enqueue", fail)
    before = db.cases.count_documents({"student_id": uid("student_a")})
    with pytest.raises(RuntimeError):
        service.create(
            uid("student_a"), "student", "finance", "Synthetic transaction request", "a" * 64
        )
    assert db.cases.count_documents({"student_id": uid("student_a")}) == before
    assert db.submission_keys.count_documents({"user_id": uid("student_a")}) == 0
    assert (
        db.audit_events.count_documents({"actor_id": uid("student_a"), "action": "case_submitted"})
        == 0
    )
    monkeypatch.setattr(Outbox, "enqueue", original)
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(
            pool.map(
                lambda _: service.create(
                    uid("student_a"),
                    "student",
                    "finance",
                    "Synthetic transaction request",
                    "a" * 64,
                ),
                range(2),
            )
        )
    assert (
        ids[0] == ids[1]
        and db.cases.count_documents({"student_id": uid("student_a")}) == before + 1
    )


def test_empty_and_pagination_scoped_to_student(bundle, student_app):
    db, uid = bundle
    app, browser, routing = student_app
    client = browser()
    db.cases.update_many({"student_id": uid("student_a")}, {"$set": {"archive_state": "archived"}})
    assert b"No support requests yet" in client.get("/cases").data
    service = StudentCases(app.extensions["mongo"].student_support_test, routing)
    for i in range(22):
        service.create(
            uid("student_a"),
            "student",
            "finance",
            "Synthetic pagination " + str(i),
            format(i, "064x"),
        )
    response = client.get("/cases")
    assert response.status_code == 200 and response.data.count(b'class="case-card"') == 20
    next_url = re.search(rb'href="([^"]+after=[^"]+)"', response.data)[1].decode()
    older = client.get(next_url)
    assert older.status_code == 200 and older.data.count(b'class="case-card"') == 2
    assert b"SS-DEMO-CASE_B" not in older.data
    assert browser("student_b").get(next_url).status_code == 400
    assert client.get("/cases?after=forged").status_code == 400
    assert browser("administrator", "admin").get("/cases").status_code == 403


def test_browser_and_api_line_endings_replay_same_case(student_app):
    _, browser, _ = student_app
    client = browser()
    data = form(client)
    response = client.post(
        "/cases/new", data={**data, "description": "Synthetic first line\r\nSecond line"}
    )
    replay = client.post(
        "/cases/new", data={**data, "description": "Synthetic first line\nSecond line"}
    )
    assert (
        response.status_code == replay.status_code == 303 and response.location == replay.location
    )


def test_ten_thousand_unicode_characters_fit_encoded_form_limit(student_app):
    _, browser, _ = student_app
    client = browser()
    data = form(client)
    response = client.post("/cases/new", data={**data, "description": "🌿" * 10000})
    assert response.status_code == 303
    assert client.get(response.location).status_code == 200


def test_request_form_body_still_has_explicit_upper_bound(student_app):
    _, browser, _ = student_app
    client = browser()
    response = client.post(
        "/cases/new", data=b"x" * (128 * 1024 + 1), content_type="application/x-www-form-urlencoded"
    )
    assert response.status_code == 413
