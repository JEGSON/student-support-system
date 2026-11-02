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
    assert all(row["_id"] != rid for row in r.list(uid("manager_disability"), "staff"))


@pytest.mark.parametrize(
    "source_team,target_team,officer,source_manager,target_manager",
    [
        (
            "accommodation",
            "wellbeing",
            "officer_accommodation",
            "manager_accommodation",
            "manager_wellbeing",
        ),
        ("disability", "academic", "officer_other", "manager_disability", "manager_academic"),
    ],
)
def test_required_cross_team_scenarios(
    bundle, source_team, target_team, officer, source_manager, target_manager
):
    db, uid = bundle
    db.cases.update_one(
        {"_id": uid("case_a")},
        {
            "$set": {
                "team_id": uid("team_" + source_team),
                "category": source_team,
                "assignee_id": uid(officer),
            }
        },
    )
    service = Referrals(db)
    proposal = service.propose(
        uid(officer),
        "staff",
        uid("case_a"),
        uid("team_" + target_team),
        target_team,
        "Synthetic " + source_team + " to " + target_team,
        "Minimal selected synthetic summary",
    )
    service.decide(uid(source_manager), "staff", proposal, "approve", "Scoped source approval")
    created = service.decide(
        uid(target_manager), "staff", proposal, "accept", "Scoped target acceptance"
    )
    assert db.cases.find_one({"_id": created})["category"] == target_team


def test_reassigned_proposer_loses_outgoing_summary_access(bundle):
    db, uid = bundle
    service = Referrals(db)
    proposal = service.propose(
        uid("officer_assigned"),
        "staff",
        uid("case_a"),
        uid("team_disability"),
        "disability",
        "Purpose",
        "Minimal summary",
    )
    db.cases.update_one(
        {"_id": uid("case_a")}, {"$set": {"assignee_id": uid("officer_unassigned")}}
    )
    assert all(row["_id"] != proposal for row in service.list(uid("officer_assigned"), "staff"))
