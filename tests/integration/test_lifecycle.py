import os
from datetime import timedelta

import pytest

from app.repositories.core import utc_now
from app.services.access import AccessService
from app.services.lifecycle import POLICY, Lifecycle
from app.services.policy import AccessDenied

pytestmark = [
    pytest.mark.runtime,
    pytest.mark.skipif(os.getenv("RUN_RUNTIME") != "1", reason="Local replica set"),
]


def old_closed(db, uid):
    db.cases.update_one(
        {"_id": uid("case_a")},
        {"$set": {"status": "Closed", "closed_at": utc_now() - timedelta(days=2)}},
    )


def test_departure_review_archive_read_and_hold(bundle):
    db, uid = bundle
    lifecycle = Lifecycle(db)
    AccessService(db).membership(
        uid("administrator"),
        "admin",
        uid("officer_assigned"),
        uid("team_finance"),
        "officer",
        False,
        "Synthetic departure",
    )
    assert any(
        r["_id"] == uid("case_a") for r in lifecycle.reassignment(uid("manager_finance"), "staff")
    )
    old_closed(db, uid)
    case = db.cases.find_one({"_id": uid("case_a")})
    lifecycle.archive(uid("manager_finance"), "staff", uid("case_a"), case["version"])
    assert lifecycle.archive_read(
        uid("manager_finance"), "staff", uid("case_a"), "Synthetic audit"
    )["reference"]
    assert (
        db.audit_events.find_one({"action": "archive_read", "target_id": uid("case_a")})["purpose"]
        == "Synthetic audit"
    )
    with pytest.raises(AccessDenied):
        lifecycle.archive_read(uid("manager_disability"), "staff", uid("case_a"), "Wrong scope")
    lifecycle.hold(uid("administrator"), "admin", uid("case_a"), True, "Synthetic legal hold")
    with pytest.raises(AccessDenied):
        lifecycle.request(uid("administrator"), "admin", uid("case_a"), POLICY, "Held request")


def test_disposal_independent_approval_atomic_linked_cleanup_and_repeat(bundle):
    db, uid = bundle
    lifecycle = Lifecycle(db)
    old_closed(db, uid)
    lifecycle.archive(uid("manager_finance"), "staff", uid("case_a"), 1)
    record = lifecycle.request(
        uid("administrator"), "admin", uid("case_a"), POLICY, "Synthetic policy exercise"
    )
    with pytest.raises(AccessDenied):
        lifecycle.approve(uid("administrator"), "admin", record)
    with pytest.raises(AccessDenied):
        lifecycle.execute(record)
    lifecycle.approve(uid("approver"), "admin", record)
    lifecycle.execute(record)
    lifecycle.execute(record)
    assert not db.cases.find_one({"_id": uid("case_a")})
    for name in ["messages", "internal_notes", "case_events", "notification_outbox"]:
        assert db[name].count_documents({"case_id": uid("case_a")}) == 0
    assert db.disposal_records.find_one({"_id": record})["state"] == "completed"
    assert db.audit_events.find_one({"target_id": uid("case_a"), "action": "case_disposed"})


def test_unconfigured_policy_and_recent_case_refuse(bundle):
    db, uid = bundle
    lifecycle = Lifecycle(db)
    with pytest.raises(AccessDenied):
        lifecycle.request(
            uid("administrator"), "admin", uid("case_a"), "real-policy", "No real policy"
        )
    with pytest.raises(AccessDenied):
        lifecycle.request(
            uid("administrator"), "admin", uid("case_a"), POLICY, "Not archived or old"
        )
