import os
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
import requests
from dotenv import dotenv_values

from app.repositories.core import utc_now
from app.services.outbox import Outbox
from app.services.transactions import transaction
from scripts.database_setup import local_client
from worker.delivery import LocalDelivery

pytestmark = [
    pytest.mark.runtime,
    pytest.mark.skipif(os.getenv("RUN_RUNTIME") != "1", reason="Local capture and database"),
]


@pytest.fixture
def delivery(bundle):
    db, uid = bundle
    contact = uid("student_a") + "@example.invalid"
    db.users.update_one({"_id": uid("student_a")}, {"$set": {"verified_contact": contact}})
    transaction(
        db,
        lambda sid: Outbox(db).enqueue(
            sid, str(uuid4()), uid("student_a"), uid("case_a"), "case_received"
        ),
    )
    job = db.notification_outbox.find_one({"case_id": uid("case_a")})
    db.notification_outbox.update_one(
        {"_id": job["_id"]}, {"$set": {"next_attempt_at": utc_now() - timedelta(days=2)}}
    )
    client = local_client(dotenv_values(Path(__file__).resolve().parents[2] / ".env"), "worker")
    yield (
        db,
        uid,
        LocalDelivery(client.student_support_test, uid("worker"), "http://127.0.0.1:5050"),
        job,
        contact,
    )
    client.close()


def test_actual_local_capture_generic_content(delivery):
    db, uid, worker, job, contact = delivery
    assert worker.once() == "sent"
    response = requests.get("http://127.0.0.1:8025/api/v1/messages", timeout=3)
    response.raise_for_status()
    capture = next(
        m for m in response.json()["messages"] if any(t["Address"] == contact for t in m["To"])
    )
    message = requests.get(
        "http://127.0.0.1:8025/api/v1/message/" + capture["ID"], timeout=3
    ).json()
    text = message["Text"]
    assert (
        "/cases" in text
        and "finance" not in text.lower()
        and "SYNTHETIC_NOTE" not in text
        and "description" not in text.lower()
    )
    assert db.notification_outbox.find_one({"_id": job["_id"]})["state"] == "sent"
    # Remove only this test's captured message, never a developer's capture inbox.
    requests.delete(
        "http://127.0.0.1:8025/api/v1/messages", json={"IDs": [capture["ID"]]}, timeout=3
    ).raise_for_status()


def test_provider_failure_keeps_case_and_retries(delivery, monkeypatch):
    db, uid, worker, job, _ = delivery

    def fail(msg):
        raise OSError("Synthetic SMTP outage")

    monkeypatch.setattr(worker, "send", fail)
    assert worker.once() == "retry" and db.cases.find_one({"_id": uid("case_a")})
    assert db.notification_outbox.find_one({"_id": job["_id"]})["state"] == "pending"


@pytest.mark.parametrize("reason", ["disabled", "expired", "unapproved_contact"])
def test_ineligible_notifications_never_send(delivery, monkeypatch, reason):
    db, uid, worker, job, _ = delivery
    if reason == "disabled":
        db.users.update_one({"_id": uid("student_a")}, {"$set": {"account_status": "disabled"}})
    elif reason == "expired":
        db.notification_outbox.update_one(
            {"_id": job["_id"]}, {"$set": {"expires_at": utc_now() - timedelta(seconds=1)}}
        )
    else:
        db.users.update_one(
            {"_id": uid("student_a")},
            {"$set": {"verified_contact": "not-for-delivery@university.example"}},
        )
    sent = []
    monkeypatch.setattr(worker, "send", lambda msg: sent.append(msg))
    assert worker.once() == "discarded" and not sent


def test_crash_after_send_releases_to_duplicate_with_stable_message_id(delivery, monkeypatch):
    db, uid, worker, job, _ = delivery
    sent = []
    monkeypatch.setattr(worker, "send", lambda msg: sent.append(msg["Message-ID"]))
    original = worker.jobs.finish

    def crash(*args, **kwargs):
        raise RuntimeError("Synthetic crash after send")

    monkeypatch.setattr(worker.jobs, "finish", crash)
    with pytest.raises(RuntimeError):
        worker.once()
    db.notification_outbox.update_one(
        {"_id": job["_id"]}, {"$set": {"lease_until": utc_now() - timedelta(seconds=1)}}
    )
    monkeypatch.setattr(worker.jobs, "finish", original)
    assert worker.once() == "sent" and len(sent) == 2 and sent[0] == sent[1]
