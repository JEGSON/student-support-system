import os
from uuid import uuid4

import pytest

from app.services.communication import Communication
from app.services.outbox import Outbox
from app.services.policy import AccessDenied
from app.services.staff_cases import StaffCases

pytestmark = [
    pytest.mark.runtime,
    pytest.mark.skipif(os.getenv("RUN_RUNTIME") != "1", reason="Local replica set"),
]


def test_full_question_reply_note_close_reopen_and_corrections(bundle):
    db, uid = bundle
    c = Communication(db)
    case = uid("case_a")
    officer = uid("officer_assigned")
    student = uid("student_a")
    manager = uid("manager_finance")
    StaffCases(db).mutate(officer, "staff", case, 1, "start", reason="Begin synthetic support")
    c.act(officer, "staff", case, 2, "question", body="Synthetic information request")
    assert db.cases.find_one({"_id": case})["status"] == "Awaiting Student"
    mid = c.act(student, "student", case, 3, "message", body="Synthetic reply", key_hash="a" * 64)
    assert db.cases.find_one({"_id": case})["status"] == "In Progress"
    assert (
        c.act(student, "student", case, 3, "message", body="Synthetic reply", key_hash="a" * 64)
        == mid
    )
    note = c.act(officer, "staff", case, 4, "note", body="SYNTHETIC_PRIVATE_NOTE")
    c.act(officer, "staff", case, 5, "note", body="Corrected private note", correction=note)
    messages, _, version = c.thread(student, "student", case)
    assert "SYNTHETIC_PRIVATE_NOTE" not in str(messages) and len(messages) >= 2
    with pytest.raises(AccessDenied):
        c.thread(student, "student", case, notes=True)
    c.act(
        student,
        "student",
        case,
        version,
        "message",
        body="Corrected reply",
        correction=mid,
        key_hash="b" * 64,
    )
    version += 1
    c.act(officer, "staff", case, version, "close", body="Synthetic outcome recorded")
    closed = db.cases.find_one({"_id": case})
    assert closed["status"] == "Closed" and closed["resolution_message_id"]
    with pytest.raises(AccessDenied):
        c.act(student, "student", case, version + 1, "message", body="Blocked")
    with pytest.raises(AccessDenied):
        c.act(officer, "staff", case, version + 1, "reopen", reason="Not manager")
    c.act(
        manager,
        "staff",
        case,
        version + 1,
        "reopen",
        reason="Reviewed synthetic reopening",
        assignee=officer,
    )
    assert db.cases.find_one({"_id": case})["status"] == "In Progress"
    assert db.messages.find_one({"_id": mid})["body"] == "Synthetic reply"


@pytest.mark.parametrize("operation", ["question", "close", "resume", "reopen"])
def test_forbidden_initial_transitions(bundle, operation):
    db, uid = bundle
    with pytest.raises((AccessDenied, ValueError)):
        Communication(db).act(
            uid("manager_finance"),
            "staff",
            uid("case_a"),
            1,
            operation,
            body="Synthetic text",
            reason="Synthetic reason",
        )
    assert db.cases.find_one({"_id": uid("case_a")})["version"] == 1


def test_no_forged_correction_and_rollback(bundle, monkeypatch):
    db, uid = bundle
    c = Communication(db)
    case = uid("case_a")
    with pytest.raises(AccessDenied):
        c.act(uid("student_b"), "student", case, 1, "message", body="Forbidden")
    with pytest.raises(AccessDenied):
        c.act(
            uid("student_a"),
            "student",
            case,
            1,
            "message",
            body="Bad correction",
            correction=str(uuid4()),
        )

    def fail(*args, **kwargs):
        raise RuntimeError("Synthetic outbox failure")

    monkeypatch.setattr(Outbox, "enqueue", fail)
    before = db.messages.count_documents({"case_id": case})
    with pytest.raises(RuntimeError):
        c.act(uid("student_a"), "student", case, 1, "message", body="Rollback me")
    assert (
        db.messages.count_documents({"case_id": case}) == before
        and db.cases.find_one({"_id": case})["version"] == 1
    )
