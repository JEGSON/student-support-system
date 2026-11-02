import os
from datetime import timedelta

import pytest

from app.repositories.core import utc_now
from app.services.access import AccessService
from app.services.policy import AccessDenied
from app.services.staff_cases import StaffCases
from app.services.transactions import VersionConflict

pytestmark = [
    pytest.mark.runtime,
    pytest.mark.skipif(os.getenv("RUN_RUNTIME") != "1", reason="Local replica set"),
]


def test_scoped_queue_and_staff_denial(bundle):
    db, uid = bundle
    s = StaffCases(db)
    rows, _ = s.queue(uid("triage"), "staff")
    assert rows and all("description" not in r and "student_id" not in r for r in rows)
    for actor in ["officer_unassigned", "manager_disability", "administrator"]:
        with pytest.raises(AccessDenied):
            s.read(uid(actor), "staff", uid("case_a"))
    assert s.read(uid("officer_assigned"), "staff", uid("case_a"))["reference"]


def test_assign_start_reassign_version_and_revoke(bundle):
    db, uid = bundle
    s = StaffCases(db)
    s.mutate(
        uid("manager_finance"),
        "staff",
        uid("case_a_second"),
        1,
        "assign",
        assignee=uid("officer_assigned"),
        reason="Assign synthetic work",
    )
    case = db.cases.find_one({"_id": uid("case_a_second")})
    assert case["status"] == "New"
    with pytest.raises(VersionConflict):
        s.mutate(uid("manager_finance"), "staff", case["_id"], 1, "start", reason="Stale action")
    s.mutate(uid("officer_assigned"), "staff", case["_id"], 2, "start", reason="Begin support")
    s.mutate(
        uid("manager_finance"),
        "staff",
        case["_id"],
        3,
        "assign",
        assignee=uid("officer_unassigned"),
        reason="Reassign support",
    )
    with pytest.raises(AccessDenied):
        s.read(uid("officer_assigned"), "staff", case["_id"])
    assert s.read(uid("officer_unassigned"), "staff", case["_id"])
    with pytest.raises(Exception) as error:
        s.mutate(
            uid("manager_finance"),
            "staff",
            case["_id"],
            4,
            "assign",
            assignee=uid("officer_other"),
            reason="Wrong team",
        )
    assert isinstance(error.value, ValueError)


def test_claim_expiry_route_release_and_competition(bundle):
    db, uid = bundle
    s = StaffCases(db)
    a = AccessService(db)
    a.claim(uid("triage"), "staff", uid("case_a"))
    case = s.read(uid("triage"), "staff", uid("case_a"), triage=True)
    assert "messages" not in case and "notes" not in case
    with pytest.raises(AccessDenied):
        a.claim(uid("manager_finance"), "staff", uid("case_a"))
    s.release(uid("triage"), "staff", uid("case_a"))
    with pytest.raises(AccessDenied):
        s.read(uid("triage"), "staff", uid("case_a"), triage=True)
    a.claim(uid("triage"), "staff", uid("case_a"))
    db.triage_claims.update_one(
        {"case_id": uid("case_a")}, {"$set": {"expires_at": utc_now() - timedelta(seconds=1)}}
    )
    with pytest.raises(AccessDenied):
        s.read(uid("triage"), "staff", uid("case_a"), triage=True)
