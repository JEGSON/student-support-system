"""HTTP and operational gaps found by the 4 November function walkthrough."""

import os
import re
import secrets
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import dotenv_values
from pymongo.errors import PyMongoError

from app import create_app
from app.auth.sessions import COOKIE, token_hash
from app.repositories.core import InvalidInput, Repositories, utc_now
from app.services.account_privacy import AccountPrivacy
from app.services.enrolment import Enrolment
from app.services.staff_cases import StaffCases
from scripts.database_setup import local_client
from worker.delivery import LocalDelivery

pytestmark = [
    pytest.mark.runtime,
    pytest.mark.skipif(os.getenv("RUN_RUNTIME") != "1", reason="Isolated local replica set"),
]
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def clients(bundle):
    db, uid = bundle
    values = dict(dotenv_values(ROOT / ".env"))
    app = create_app(
        {
            **values,
            "APP_ENV": "testing",
            "MONGODB_DATABASE": "student_support_test",
            "SELF_REGISTRATION_ENABLED": "1",
        }
    )
    app.extensions["mongo"].close()
    web = local_client(values, "web_testing")
    app.extensions["mongo"] = web

    def make(actor, context):
        raw = secrets.token_urlsafe(32)
        now = utc_now()
        db.sessions.insert_one(
            {
                "_id": str(uuid4()),
                "user_id": uid(actor),
                "token_hash": token_hash(raw),
                "created_at": now,
                "last_seen_at": now,
                "idle_expires_at": now + timedelta(minutes=30),
                "absolute_expires_at": now + timedelta(hours=8),
                "authentication_time": now,
                "version": 0,
                "data": {"context": context},
            }
        )
        client = app.test_client()
        client.set_cookie(COOKIE, raw)
        response = client.get("/account")
        assert response.status_code == 200
        csrf = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)[1].decode()
        return client, csrf

    yield app, make
    web.close()


def test_triage_claim_read_release_and_invalid_fields_http(bundle, clients):
    db, uid = bundle
    _, make = clients
    client, csrf = make("triage", "staff")
    case = uid("case_a")
    assert client.get(f"/staff/triage/{case}").status_code == 404
    assert (
        client.post(
            f"/staff/cases/{case}/claim", data={"csrf_token": csrf, "unexpected": "x"}
        ).status_code
        == 400
    )
    assert client.post(f"/staff/cases/{case}/claim", data={"csrf_token": csrf}).status_code == 303
    response = client.get(f"/staff/triage/{case}")
    assert response.status_code == 200 and b"Initial request routing" in response.data
    assert b"SYNTHETIC_NOTE" not in response.data
    assert (
        client.post(f"/staff/triage/{case}/release", data={"csrf_token": csrf}).status_code == 303
    )
    assert db.triage_claims.find_one({"case_id": case})["state"] == "released"
    assert client.get(f"/staff/triage/{case}").status_code == 404


def test_manager_reassignment_archive_and_purpose_audit_http(bundle, clients):
    db, uid = bundle
    _, make = clients
    manager, csrf = make("manager_finance", "staff")
    row = db.cases.find_one({"_id": uid("case_a")})
    db.memberships.update_many(
        {"user_id": row["assignee_id"], "team_id": row["team_id"]}, {"$set": {"active": False}}
    )
    response = manager.get("/staff/reassignment")
    assert response.status_code == 200 and row["reference"].encode() in response.data
    db.cases.update_one(
        {"_id": row["_id"]},
        {"$set": {"status": "Closed", "closed_at": utc_now() - timedelta(days=2)}},
    )
    url = f"/staff/cases/{row['_id']}/archive"
    assert manager.post(url, data={"csrf_token": csrf, "version": "0"}).status_code == 409
    assert (
        manager.post(url, data={"csrf_token": csrf, "version": str(row["version"])}).status_code
        == 303
    )
    assert manager.get("/staff/archive").status_code == 200
    assert (
        manager.post(
            "/staff/archive", data={"csrf_token": csrf, "case": row["_id"], "purpose": ""}
        ).status_code
        == 400
    )
    response = manager.post(
        "/staff/archive",
        data={"csrf_token": csrf, "case": row["_id"], "purpose": "Synthetic reviewed follow-up"},
    )
    assert response.status_code == 200 and row["description"].encode() in response.data
    assert b"SYNTHETIC_NOTE" not in response.data
    assert db.audit_events.find_one({"actor_id": uid("manager_finance"), "action": "archive_read"})
    outsider, other_csrf = make("manager_disability", "staff")
    assert (
        outsider.post(
            "/staff/archive",
            data={"csrf_token": other_csrf, "case": row["_id"], "purpose": "Wrong team"},
        ).status_code
        == 404
    )


def test_admin_privacy_retention_invitation_revoke_http(bundle, clients):
    db, uid = bundle
    app, make = clients
    admin, csrf = make("administrator", "admin")
    assert admin.get("/privacy").status_code == 200
    record = AccountPrivacy(db, app.config["IDENTITY_FINGERPRINT_KEY"]).close(
        uid("student_a"), 0, int(utc_now().timestamp())
    )
    response = admin.get("/access/privacy")
    assert response.status_code == 200 and record["_id"].encode() in response.data
    form = {
        "csrf_token": csrf,
        "request": record["_id"],
        "reason": "Synthetic policy review",
        "policy": "TEST-REVIEW-1",
        "days": "0",
    }
    assert admin.post("/access/privacy", data=form).status_code == 400
    assert admin.post("/access/privacy", data={**form, "days": "30"}).status_code == 303
    assert db.account_closures.find_one({"_id": record["_id"]})["state"] == "retained"
    assert admin.get("/retention").status_code == 200
    invitation, _ = Enrolment(db).create(
        uid("administrator"),
        "admin",
        app.config["OIDC_ISSUER"],
        "review@example.invalid",
        "student",
    )
    assert (
        admin.post(
            "/access/invitations",
            data={"csrf_token": csrf, "operation": "revoke", "invitation": invitation["_id"]},
        ).status_code
        == 303
    )
    assert db.enrolment_invitations.find_one({"_id": invitation["_id"]})["state"] == "revoked"
    student, _ = make("student_b", "student")
    for url in ["/access/privacy", "/retention", "/access/invitations"]:
        assert student.get(url).status_code == 403


def test_staff_denied_invalid_and_database_unavailable_http(bundle, clients, monkeypatch):
    _, uid = bundle
    _, make = clients
    manager, _ = make("manager_disability", "staff")
    response = manager.get(f"/staff/cases/{uid('case_a')}")
    assert response.status_code == 404 and b"Request unavailable" in response.data
    assert manager.get("/staff?unexpected=x").status_code == 400

    def outage(*args, **kwargs):
        raise PyMongoError("PRIVATE_DATABASE_ERROR_MUST_NOT_LEAK")

    monkeypatch.setattr(StaffCases, "queue", outage)
    response = manager.get("/staff")
    assert response.status_code == 503 and b"Service temporarily unavailable" in response.data
    assert b"PRIVATE_DATABASE_ERROR_MUST_NOT_LEAK" not in response.data


def test_repository_identity_lookup_and_worker_alert_counts(bundle):
    db, uid = bundle
    repo = Repositories(db)
    assert repo.get_user(uid("student_a"))["_id"] == uid("student_a")
    with pytest.raises(InvalidInput):
        repo.get_user({"$ne": None})
    worker = LocalDelivery(db, uid("worker"), "http://127.0.0.1:5050")
    baseline = worker.alerts()
    for state in ["dead", "pending"]:
        db.notification_outbox.insert_one(
            {
                "_id": str(uuid4()),
                "event_key": "review-" + uuid4().hex,
                "recipient_user_id": uid("student_a"),
                "case_id": uid("case_a"),
                "template_key": "case_updated",
                "channel": "email",
                "state": state,
                "attempts": 0,
                "next_attempt_at": utc_now(),
                "created_at": utc_now() - timedelta(minutes=16),
            }
        )
    assert worker.alerts() == {"dead": baseline["dead"] + 1, "overdue": baseline["overdue"] + 1}
