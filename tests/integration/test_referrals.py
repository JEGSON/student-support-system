import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.services.policy import AccessDenied
from app.services.referrals import Referrals
from app.services.staff_cases import StaffCases

pytestmark = [
    pytest.mark.runtime,
    pytest.mark.skipif(os.getenv("RUN_RUNTIME") != "1", reason="Local replica set"),
]


def test_minimal_referral_concurrent_acceptance_source_unchanged(bundle):
    db, uid = bundle
    r = Referrals(db)
    rid = r.propose(
        uid("officer_assigned"),
        "staff",
        uid("case_a"),
        uid("team_disability"),
        "disability",
        "Synthetic purpose",
        "Only this deliberate summary",
    )
    assert not r.list(uid("manager_disability"), "staff")
    with pytest.raises(AccessDenied):
        r.decide(uid("manager_disability"), "staff", rid, "accept", "Before approval")
    r.decide(uid("manager_finance"), "staff", rid, "approve", "Reviewed minimal sharing")
    rows = r.list(uid("manager_disability"), "staff")
    assert rows[0]["summary"] == "Only this deliberate summary"
    assert "description" not in rows[0] and "notes" not in str(rows)
    source = db.cases.find_one({"_id": uid("case_a")})
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(
            pool.map(
                lambda _: r.decide(
                    uid("manager_disability"), "staff", rid, "accept", "Target accepted"
                ),
                range(2),
            )
        )
    assert ids[0] == ids[1] and db.cases.count_documents({"originating_referral_id": rid}) == 1
    assert db.cases.find_one({"_id": uid("case_a")}) == source
    target = db.cases.find_one({"_id": ids[0]})
    assert (
        target["student_id"] == uid("student_a")
        and target["description"] == "Only this deliberate summary"
        and target["status"] == "New"
        and target["assignee_id"] is None
    )
    with pytest.raises(AccessDenied):
        StaffCases(db).read(uid("manager_disability"), "staff", uid("case_a"))


def test_referral_reject_withdraw_and_wrong_scope(bundle):
    db, uid = bundle
    r = Referrals(db)
    with pytest.raises(AccessDenied):
        r.propose(
            uid("officer_unassigned"),
            "staff",
            uid("case_a"),
            uid("team_disability"),
            "disability",
            "Purpose",
            "Summary",
        )
    rid = r.propose(
        uid("officer_assigned"),
        "staff",
        uid("case_a"),
        uid("team_disability"),
        "disability",
        "Purpose",
        "Summary",
    )
    with pytest.raises(AccessDenied):
        r.decide(uid("manager_disability"), "staff", rid, "approve", "Wrong scope")
    r.decide(uid("manager_finance"), "staff", rid, "approve", "Source approved")
    r.decide(uid("manager_disability"), "staff", rid, "reject", "Target rejected")
    with pytest.raises(AccessDenied):
        r.decide(uid("manager_disability"), "staff", rid, "accept", "Cannot accept rejected")
    rid = r.propose(
        uid("officer_assigned"),
        "staff",
        uid("case_a"),
        uid("team_disability"),
        "disability",
        "Purpose",
        "Summary",
    )
    r.decide(uid("manager_finance"), "staff", rid, "withdraw", "Withdrawn before sharing")
    assert db.referrals.find_one({"_id": rid})["status"] == "withdrawn"
