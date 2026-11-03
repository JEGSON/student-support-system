import os
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from dotenv import dotenv_values

from app.operations.recovery import capture, restore
from app.repositories.core import utc_now
from app.repositories.schema import SCHEMAS, install_schema
from app.services.account_privacy import AccountPrivacy, fingerprint
from app.services.accounts import Accounts
from app.services.audit import AuditWriter
from app.services.policy import AccessDenied
from scripts.database_setup import local_client

pytestmark = [
    pytest.mark.runtime,
    pytest.mark.skipif(os.getenv("RUN_RUNTIME") != "1", reason="Local replica set"),
]
KEY = "private-test-fingerprint-key-" * 3


def test_closure_erases_profile_revokes_access_preserves_case_and_blocks_reenrolment(bundle):
    db, uid = bundle
    before = db.users.find_one({"_id": uid("student_a")})
    db.users.update_one(
        {"_id": uid("student_a")},
        {"$set": {"verified_contact": "person@example.invalid", "course_label": "Private course"}},
    )
    db.notification_outbox.insert_one(
        {
            "_id": str(uuid4()),
            "event_key": "closure-" + uuid4().hex,
            "recipient_user_id": uid("student_a"),
            "case_id": uid("case_a"),
            "template_key": "case_updated",
            "channel": "email",
            "state": "pending",
            "attempts": 0,
            "next_attempt_at": utc_now(),
            "created_at": utc_now(),
        }
    )
    original_case = db.cases.find_one({"_id": uid("case_a")})
    privacy = AccountPrivacy(db, KEY)
    for timestamp in [
        None,
        int((utc_now() - timedelta(minutes=6)).timestamp()),
        int((utc_now() + timedelta(seconds=30)).timestamp()),
    ]:
        with pytest.raises(AccessDenied):
            privacy.close(uid("student_a"), 0, timestamp)
    record = privacy.close(uid("student_a"), 0, int(utc_now().timestamp()))
    assert record["state"] == "review_required"
    user = db.users.find_one({"_id": uid("student_a")})
    assert (
        user["account_status"] == "closed"
        and user["global_roles"] == []
        and user["display_name"] == "Closed account"
    )
    assert all(k not in user for k in ["student_reference", "course_label", "verified_contact"])
    assert user["identity_subject"] != before["identity_subject"]
    assert db.cases.find_one({"_id": uid("case_a")}) == original_case
    assert (
        db.notification_outbox.count_documents(
            {"recipient_user_id": uid("student_a"), "state": {"$in": ["pending", "leased"]}}
        )
        == 0
    )
    with pytest.raises(AccessDenied):
        Accounts(db, {"IDENTITY_FINGERPRINT_KEY": KEY}).resolve(
            before["identity_issuer"], {"sub": before["identity_subject"]}, allow_registration=True
        )
    privacy.record_retention(
        uid("administrator"),
        "admin",
        record["_id"],
        "Pending approved case-retention review",
        "University-policy-test",
        30,
    )
    row = db.account_closures.find_one({"_id": record["_id"]})
    assert row["state"] == "retained" and row["review_due_at"] > utc_now()
    with pytest.raises(AccessDenied):
        privacy.review(uid("student_b"), "student")


def test_closure_without_cases_and_required_audit_rollback(bundle, monkeypatch):
    db, uid = bundle
    key = str(uuid4())
    original = {
        **db.users.find_one({"_id": uid("student_a")}),
        "_id": key,
        "identity_subject": "privacy/" + key,
    }
    original.pop("student_reference", None)
    db.users.insert_one(original)
    try:

        def fail(*args, **kwargs):
            raise RuntimeError("Synthetic audit failure")

        with monkeypatch.context() as scoped:
            scoped.setattr(AuditWriter, "append", fail)
            with pytest.raises(RuntimeError):
                AccountPrivacy(db, KEY).close(key, 0, int(utc_now().timestamp()))
        assert db.users.find_one({"_id": key}) == original and not db.account_closures.find_one(
            {"user_id": key}
        )
        row = AccountPrivacy(db, KEY).close(key, 0, int(utc_now().timestamp()))
        assert row["state"] == "profile_erased"
        with pytest.raises(AccessDenied):
            AccountPrivacy(db, KEY).close(uid("administrator"), 0, int(utc_now().timestamp()))
        with pytest.raises(AccessDenied):
            AccountPrivacy(db, KEY).close(uid("officer_assigned"), 0, int(utc_now().timestamp()))
    finally:
        db.account_closures.delete_many({"user_id": key})
        db.audit_events.delete_many({"actor_id": key})
        db.users.delete_one({"_id": key})


def test_restore_reapplies_account_closure_and_revokes_invitation_codes(bundle, tmp_path):
    db, uid = bundle
    before = db.users.find_one({"_id": uid("student_a")})
    encryption = Fernet.generate_key()
    backup = tmp_path / "snapshot"
    ledger = tmp_path / "ledger"
    capture(db, encryption, backup)
    record = AccountPrivacy(db, KEY).close(uid("student_a"), 0, int(utc_now().timestamp()))
    capture(db, encryption, ledger, True)
    values = dotenv_values(Path(__file__).resolve().parents[2] / ".env")
    with local_client(values, "schema") as schema:
        install_schema(schema.student_support_restore_test)
    with local_client(values, "restore") as client:
        target = client.student_support_restore_test
        for name in SCHEMAS:
            target[name].delete_many({})
        try:
            result = restore(target, encryption, backup, ledger)
            assert result["account_closures_replayed"] >= 1
            restored = target.users.find_one({"_id": uid("student_a")})
            assert restored["account_status"] == "closed" and "verified_contact" not in restored
            assert restored["identity_fingerprint"] == fingerprint(
                before["identity_issuer"], before["identity_subject"], KEY
            )
            assert target.account_closures.find_one({"_id": record["_id"]})
        finally:
            for name in SCHEMAS:
                target[name].delete_many({})
