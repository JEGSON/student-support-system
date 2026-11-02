"""Stage 07: real MongoDB rollback, guards, retries, audit and DB privileges."""

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import dotenv_values
from pymongo.errors import DuplicateKeyError, OperationFailure

from app.repositories.core import utc_now
from app.services.access import AccessService
from app.services.audit import AuditReader, AuditWriter
from app.services.case_transactions import CaseTransactions
from app.services.outbox import NotificationJobs, Outbox
from app.services.policy import AccessDenied
from app.services.submissions import idempotent
from app.services.transactions import VersionConflict, transaction
from scripts.database_setup import local_client

pytestmark = [
    pytest.mark.runtime,
    pytest.mark.skipif(
        os.getenv("RUN_RUNTIME") != "1", reason="Actual isolated replica set required"
    ),
]


@pytest.fixture
def restricted():
    values = dotenv_values(Path(__file__).resolve().parents[2] / ".env")
    clients = {kind: local_client(values, kind) for kind in ["web_testing", "audit", "worker"]}
    yield {kind: client.student_support_test for kind, client in clients.items()}
    for client in clients.values():
        client.close()


def change(db, uid):
    return CaseTransactions(db).change(
        uid("officer_assigned"),
        "staff",
        "update_case",
        uid("case_a"),
        1,
        {"status": "In Progress"},
        "started",
        "case_updated",
    )


@pytest.mark.parametrize("failure", ["audit", "outbox"])
def test_failure_rolls_back_case_event_audit_and_outbox(bundle, restricted, monkeypatch, failure):
    db, uid = bundle
    web = restricted["web_testing"]
    before = db.cases.find_one({"_id": uid("case_a")})

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(
        AuditWriter if failure == "audit" else Outbox,
        "append" if failure == "audit" else "enqueue",
        fail,
    )
    with pytest.raises(RuntimeError):
        change(web, uid)
    assert db.cases.find_one({"_id": uid("case_a")}) == before
    for name in ["case_events", "notification_outbox"]:
        assert db[name].count_documents({"case_id": uid("case_a")}) == 0
    assert db.audit_events.count_documents({"target_id": uid("case_a")}) == 0


def test_mutation_effects_commit_and_competing_version_denies(bundle, restricted):
    db, uid = bundle
    web = restricted["web_testing"]

    def attempt():
        try:
            change(web, uid)
            return "committed"
        except VersionConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sorted(results) == ["committed", "conflict"]
    assert db.cases.find_one({"_id": uid("case_a")})["version"] == 2
    assert db.case_events.count_documents({"case_id": uid("case_a")}) == 1
    assert db.audit_events.count_documents({"target_id": uid("case_a")}) == 1
    assert db.notification_outbox.count_documents({"case_id": uid("case_a")}) == 1


def test_real_transaction_retries_labelled_transient_failure_once(bundle, restricted):
    db, uid = bundle
    web = restricted["web_testing"]
    calls = []

    def operation(sid):
        web.cases.update_one({"_id": uid("case_a")}, {"$inc": {"version": 1}}, session=sid)
        calls.append(True)
        if len(calls) == 1:
            raise OperationFailure(
                "Synthetic transient conflict", 112, {"errorLabels": ["TransientTransactionError"]}
            )
        AuditWriter(web).append(uid("student_a"), "case_read", "case", uid("case_a"), [], sid)

    transaction(web, operation)
    assert len(calls) == 2 and db.cases.find_one({"_id": uid("case_a")})["version"] == 2
    assert db.audit_events.count_documents({"target_id": uid("case_a")}) == 1


def test_submission_key_replay_and_different_payload_conflict(bundle, restricted):
    db, uid = bundle
    web = restricted["web_testing"]
    key = hashlib.sha256(b"synthetic-key").hexdigest()
    payload = hashlib.sha256(b"synthetic-payload").hexdigest()
    calls = []

    def create():
        calls.append(True)
        return uid("case_a")

    def submit(body=payload):
        def operation(sid):
            AccessService(web).touch_user(uid("student_a"), sid)
            return idempotent(web, sid, uid("student_a"), "create_case", key, body, create)

        return transaction(web, operation)

    assert submit() == uid("case_a") and submit() == uid("case_a") and len(calls) == 1
    with pytest.raises(VersionConflict):
        submit("f" * 64)
    assert db.submission_keys.count_documents({"user_id": uid("student_a"), "key_hash": key}) == 1


def test_duplicate_outbox_key_aborts_other_business_writes(bundle, restricted):
    db, uid = bundle
    web = restricted["web_testing"]

    def operation(sid):
        web.cases.update_one({"_id": uid("case_a")}, {"$inc": {"version": 1}}, session=sid)
        for _ in range(2):
            Outbox(web).enqueue(sid, "same-event", uid("student_a"), uid("case_a"), "case_received")

    with pytest.raises(DuplicateKeyError):
        transaction(web, operation)
    assert db.cases.find_one({"_id": uid("case_a")})["version"] == 1
    assert db.notification_outbox.count_documents({"case_id": uid("case_a")}) == 0


def test_real_collection_privileges_append_only_audit_and_worker_boundaries(bundle, restricted):
    db, uid = bundle
    web = restricted["web_testing"]
    reader = restricted["audit"]
    worker = restricted["worker"]
    AuditWriter(web).append(uid("student_a"), "case_read", "case", uid("case_a"), [])
    event = db.audit_events.find_one({"target_id": uid("case_a")})
    for action in [
        lambda: web.audit_events.find_one({}),
        lambda: web.audit_events.update_one(
            {"_id": event["_id"]}, {"$set": {"action": "tampered"}}
        ),
        lambda: web.audit_events.delete_one({"_id": event["_id"]}),
        lambda: web.case_events.delete_one({"case_id": uid("case_a")}),
        lambda: reader.cases.find_one({}),
        lambda: reader.audit_events.delete_one({"_id": event["_id"]}),
        lambda: worker.cases.find_one({}),
        lambda: worker.internal_notes.find_one({}),
        lambda: worker.messages.find_one({}),
        lambda: worker.audit_events.find_one({}),
        lambda: worker.client.student_support_dev.notification_outbox.find_one({}),
        lambda: reader.client.student_support_dev.audit_events.find_one({}),
    ]:
        with pytest.raises(OperationFailure) as failure:
            action()
        assert failure.value.code == 13
    assert reader.audit_events.find_one({"_id": event["_id"]})
    assert worker.users.find_one({"_id": uid("student_a")}, {"verified_contact": 1})


def test_explicit_audit_reader_requires_scope_purpose_and_successful_read_audit(
    bundle, restricted, monkeypatch
):
    db, uid = bundle
    web = restricted["web_testing"]
    service = AccessService(web)
    grant = service.request_grant(
        uid("administrator"),
        "admin",
        uid("reviewer"),
        "audit_reviewer",
        uid("team_finance"),
        "Synthetic review",
    )
    service.approve(uid("approver"), "admin", grant, "Independent approval")
    reader = AuditReader(web, restricted["audit"])
    for case, purpose in [("case_a", ""), ("case_other", "Synthetic review")]:
        with pytest.raises(AccessDenied):
            reader.for_case(uid("reviewer"), "audit", uid(case), purpose)
    events = reader.for_case(uid("reviewer"), "audit", uid("case_a"), "Synthetic review")
    assert events and events[0]["action"] == "audit_reviewed" and "description" not in str(events)

    def fail(*args, **kwargs):
        raise RuntimeError("Audit unavailable")

    monkeypatch.setattr(AuditWriter, "append", fail)
    with pytest.raises(RuntimeError):
        reader.for_case(uid("reviewer"), "audit", uid("case_a"), "Synthetic review")


def test_jobs_lease_retry_dead_and_stale_completion(bundle, restricted):
    db, uid = bundle
    web = restricted["web_testing"]
    # Use a dedicated labelled active principal rather than a user/session context.
    principal = str(uuid4())
    db.service_principals.insert_one(
        {
            "_id": principal,
            "name": "Synthetic worker " + principal,
            "kind": "notification_worker",
            "active": True,
            "authorization_revision": 0,
        }
    )
    try:
        transaction(
            web,
            lambda sid: Outbox(web).enqueue(
                sid, str(uuid4()), uid("student_a"), uid("case_a"), "case_received"
            ),
        )
        jobs = NotificationJobs(restricted["worker"], principal)
        # Other fixture jobs may exist in a shared test DB; make this job due first.
        target = db.notification_outbox.find_one({"case_id": uid("case_a")})
        db.notification_outbox.update_one(
            {"_id": target["_id"]}, {"$set": {"next_attempt_at": utc_now() - timedelta(days=2)}}
        )
        job, token = jobs.lease()
        assert job["_id"] == target["_id"] and job["state"] == "leased" and token not in str(job)
        with pytest.raises(AccessDenied):
            jobs.finish(job["_id"], "forged", success=True)
        jobs.finish(job["_id"], token, success=False)
        saved = db.notification_outbox.find_one({"_id": job["_id"]})
        assert saved["state"] == "pending" and saved["attempts"] == 1
        db.notification_outbox.update_one(
            {"_id": job["_id"]},
            {"$set": {"attempts": 4, "next_attempt_at": utc_now() - timedelta(days=2)}},
        )
        job, token = jobs.lease()
        jobs.finish(job["_id"], token, success=False)
        assert db.notification_outbox.find_one({"_id": job["_id"]})["state"] == "dead"
        with pytest.raises(AccessDenied):
            jobs.finish(job["_id"], token, success=True)
    finally:
        db.service_principals.delete_one({"_id": principal})


def test_mutation_primitive_cannot_use_a_read_permission(bundle, restricted):
    _, uid = bundle
    with pytest.raises(AccessDenied):
        CaseTransactions(restricted["web_testing"]).change(
            uid("student_a"),
            "student",
            "read_case",
            uid("case_a"),
            1,
            {"status": "In Progress"},
            "started",
        )


def test_expired_final_lease_becomes_dead_without_delivery(bundle, restricted):
    db, uid = bundle
    principal = uid("worker")
    transaction(
        restricted["web_testing"],
        lambda sid: Outbox(restricted["web_testing"]).enqueue(
            sid, str(uuid4()), uid("student_a"), uid("case_a"), "case_received"
        ),
    )
    job = db.notification_outbox.find_one({"case_id": uid("case_a")})
    db.notification_outbox.update_one(
        {"_id": job["_id"]},
        {
            "$set": {
                "state": "leased",
                "attempts": 5,
                "lease_until": utc_now() - timedelta(seconds=1),
                "lease_hash": "0" * 64,
            }
        },
    )
    NotificationJobs(restricted["worker"], principal).lease()
    assert db.notification_outbox.find_one({"_id": job["_id"]})["state"] == "dead"
