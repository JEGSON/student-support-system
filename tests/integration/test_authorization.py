"""Role/relationship matrix and real concurrent revocation on isolated MongoDB."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from uuid import uuid4

import pytest

from app.repositories.core import utc_now
from app.services.access import AccessService
from app.services.policy import TRIAGE_FIELDS, AccessDenied, Policy, triage_view, worker_allows

pytestmark = [
    pytest.mark.runtime,
    pytest.mark.skipif(os.getenv("RUN_RUNTIME") != "1", reason="Actual replica set required"),
]


@pytest.mark.parametrize(
    "actor,context,case_label,action,allowed",
    [
        ("student_a", "student", "case_a", "read_case", True),
        ("student_b", "student", "case_a", "read_case", False),
        ("student_a", "staff", "case_a", "read_case", False),
        ("student_a", "student", "case_a", "read_notes", False),
        ("student_a", "student", "case_a", "send_message", True),
        ("student_a", "student", "case_a", "update_case", False),
        ("officer_assigned", "staff", "case_a", "read_case", True),
        ("officer_assigned", "staff", "case_a", "read_notes", True),
        ("officer_assigned", "staff", "case_a", "update_case", True),
        ("officer_assigned", "student", "case_a", "read_case", False),
        ("officer_assigned", "staff", "case_b", "read_case", False),
        ("officer_unassigned", "staff", "case_a", "read_case", False),
        ("officer_other", "staff", "case_a", "read_case", False),
        ("manager_finance", "staff", "case_a", "read_case", True),
        ("manager_finance", "staff", "case_a", "assign_case", True),
        ("manager_disability", "staff", "case_a", "read_case", False),
        ("officer_assigned", "staff", "case_a", "assign_case", False),
        ("triage", "staff", "case_a", "triage_metadata", True),
        ("triage", "staff", "case_a", "read_case", False),
        ("triage", "staff", "case_a", "read_messages", False),
        ("triage", "staff", "case_a", "read_notes", False),
        ("triage", "staff", "case_other", "triage_metadata", False),
        ("administrator", "admin", "case_a", "read_case", False),
        ("administrator", "admin", "case_a", "read_notes", False),
        ("administrator", "admin", "case_a", "manage_accounts", True),
        ("administrator", "staff", "case_a", "manage_accounts", False),
        ("approver", "admin", "case_a", "approve_grant", True),
        ("approver", "admin", "case_a", "manage_accounts", False),
        ("reviewer", "audit", "case_a", "read_case", False),
        ("reviewer", "audit", "case_a", "read_audit", False),
        ("manager_finance", "staff", "case_a", "unknown", False),
    ],
)
def test_policy_matrix(bundle, actor, context, case_label, action, allowed):
    db, uid = bundle
    case = db.cases.find_one({"_id": uid(case_label)})
    assert Policy(db, uid(actor), context).allows(action, case) == allowed


def test_disable_revocation_dual_context_and_archive(bundle):
    db, uid = bundle
    with pytest.raises(AccessDenied):
        Policy(db, uid("disabled"), "student")
    case = db.cases.find_one({"_id": uid("case_a")})
    db.memberships.update_one({"user_id": uid("officer_assigned")}, {"$set": {"active": False}})
    assert not Policy(db, uid("officer_assigned"), "staff").allows("read_case", case)
    db.users.update_one({"_id": uid("student_a")}, {"$addToSet": {"global_roles": "administrator"}})
    assert Policy(db, uid("student_a"), "student").allows("read_case", case)
    assert not Policy(db, uid("student_a"), "admin").allows("read_case", case)
    assert Policy(db, uid("student_a"), "admin").allows("manage_accounts")
    assert not Policy(db, uid("student_a"), "student").allows("manage_accounts")
    case["archive_state"] = "archived"
    assert not Policy(db, uid("student_a"), "student").allows("read_case", case)


def test_claim_is_bounded_audited_and_narrative_scope_is_narrow(bundle):
    db, uid = bundle
    service = AccessService(db)
    case = db.cases.find_one({"_id": uid("case_a")})
    assert set(triage_view(case)) == TRIAGE_FIELDS and "description" not in triage_view(case)
    assert not Policy(db, uid("triage"), "staff").allows("read_initial_request", case)
    claim = service.claim(uid("triage"), "staff", case["_id"])
    saved = db.triage_claims.find_one({"_id": claim})
    assert saved["expires_at"] - saved["created_at"] == timedelta(minutes=30)
    assert service.claim(uid("triage"), "staff", case["_id"]) == claim
    assert db.triage_claims.find_one({"_id": claim})["expires_at"] == saved["expires_at"]
    assert (
        db.audit_events.count_documents({"actor_id": uid("triage"), "action": "triage_claimed"})
        == 1
    )
    assert Policy(db, uid("triage"), "staff").allows("read_initial_request", case)
    for action in ["read_messages", "read_notes", "read_case"]:
        assert not Policy(db, uid("triage"), "staff").allows(action, case)
    with pytest.raises(AccessDenied):
        service.claim(uid("manager_finance"), "staff", case["_id"])
    db.triage_claims.update_one(
        {"_id": claim}, {"$set": {"expires_at": utc_now() - timedelta(seconds=1)}}
    )
    assert not Policy(db, uid("triage"), "staff").allows("read_initial_request", case)


def test_grants_are_independently_approved_and_audit_scoped(bundle):
    db, uid = bundle
    service = AccessService(db)
    admin, approver, target = uid("administrator"), uid("approver"), uid("student_b")
    team = uid("team_finance")
    grant = service.request_grant(
        admin, "admin", target, "audit_reviewer", team, "Synthetic access review"
    )
    with pytest.raises(AccessDenied):
        service.approve(admin, "admin", grant, "No self approval")
    # Even a requester who also has approver permission cannot self approve.
    db.users.update_one({"_id": admin}, {"$addToSet": {"global_roles": "access_approver"}})
    with pytest.raises(AccessDenied):
        service.approve(admin, "admin", grant, "Still prohibited")
    service.approve(approver, "admin", grant, "Independent review completed")
    case = db.cases.find_one({"_id": uid("case_a")})
    policy = Policy(db, target, "audit")
    assert policy.allows("read_audit", case, purpose="Synthetic audit")
    assert not policy.allows("read_audit", case)
    assert not policy.allows(
        "read_audit", db.cases.find_one({"_id": uid("case_other")}), purpose="Synthetic audit"
    )
    assert not policy.allows("read_case", case)
    with pytest.raises(AccessDenied):
        service.approve(approver, "admin", grant, "Replay")
    with pytest.raises(AccessDenied):
        service.membership(admin, "admin", target, team, "manager", True, "Bypass")
    grant = service.request_grant(admin, "admin", target, "manager", team, "Team manager")
    service.approve(approver, "admin", grant, "Reviewed")
    assert Policy(db, target, "staff").allows("assign_case", case)
    service.deactivate(admin, "admin", target, "Synthetic departure")
    with pytest.raises(AccessDenied):
        Policy(db, target, "staff")


def test_worker_is_restricted(bundle):
    db, _ = bundle
    principal = {"active": True, "kind": "notification_worker"}
    assert worker_allows(principal, "lease_notification")
    for action in ["read_case", "read_messages", "manage_accounts", "login", "read_notes"]:
        assert not worker_allows(principal, action)
    assert not worker_allows({**principal, "active": False}, "lease_notification")


def test_concurrent_revocation_rechecks_before_mutation_commit(bundle, monkeypatch):
    db, uid = bundle
    service = AccessService(db)
    checked, revoked = Event(), Event()
    original = service.touch_user
    once = [False]

    def pause(actor, sid):
        if actor == uid("officer_assigned") and not once[0]:
            once[0] = True
            checked.set()
            assert revoked.wait(10)
        return original(actor, sid)

    monkeypatch.setattr(service, "touch_user", pause)
    case_id = uid("case_a")
    before = db.cases.find_one({"_id": case_id})

    def mutation(sid, case):
        db.cases.update_one({"_id": case_id}, {"$set": {"priority": "urgent"}}, session=sid)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            service.guard, uid("officer_assigned"), "staff", "update_case", case_id, mutation
        )
        assert checked.wait(10)
        AccessService(db).membership(
            uid("administrator"),
            "admin",
            uid("officer_assigned"),
            uid("team_finance"),
            "officer",
            False,
            "Concurrent synthetic revocation",
        )
        revoked.set()
        with pytest.raises(AccessDenied):
            future.result(timeout=15)
    assert db.cases.find_one({"_id": case_id}) == before
    assert not Policy(db, uid("officer_assigned"), "staff").allows("update_case", before)


def test_revoke_privilege_removes_scope_and_manager_access(bundle):
    db, uid = bundle
    service = AccessService(db)
    admin, approver, target = uid("administrator"), uid("approver"), uid("student_b")
    team = uid("team_finance")
    case = db.cases.find_one({"_id": uid("case_a")})
    for role in ["manager", "audit_reviewer"]:
        grant = service.request_grant(admin, "admin", target, role, team, "Synthetic grant")
        service.approve(approver, "admin", grant, "Independent approval")
        service.revoke(admin, "admin", target, role, team, "Synthetic revocation")
    assert not Policy(db, target, "staff").allows("assign_case", case)
    assert not Policy(db, target, "audit").allows("read_audit", case, purpose="Review")


def test_offline_bootstrap_requires_two_provisioned_synthetic_accounts(bundle):
    from scripts.bootstrap_access import bootstrap

    db, uid = bundle
    admin, approver = uid("student_a"), uid("student_b")
    with pytest.raises(AccessDenied):
        bootstrap(db, admin, admin, "Synthetic bootstrap")
    with pytest.raises(AccessDenied):
        bootstrap(db, admin, approver, "Unprovisioned bootstrap")
    for target in [admin, approver]:
        db.users.update_one({"_id": target}, {"$set": {"identity_subject": str(uuid4())}})
    bootstrap(db, admin, approver, "Explicit offline synthetic bootstrap")
    assert Policy(db, admin, "admin").allows("manage_accounts")
    assert Policy(db, approver, "admin").allows("approve_grant")
    assert (
        db.audit_events.count_documents(
            {"action": "offline_synthetic_bootstrap", "actor_id": {"$in": [admin, approver]}}
        )
        == 2
    )
    with pytest.raises(AccessDenied):
        bootstrap(db, admin, approver, "Replay refused")


def test_access_http_grant_workflow_and_mass_assignment_denial(bundle, config):
    import re
    import secrets

    from app import create_app
    from app.auth.sessions import COOKIE, token_hash

    db, uid = bundle
    app = create_app(config)
    app.extensions["mongo"].close()
    app.extensions["mongo"] = db.client

    def browser(actor):
        token = secrets.token_urlsafe(32)
        now = utc_now()
        db.sessions.insert_one(
            {
                "_id": str(uuid4()),
                "token_hash": token_hash(token),
                "user_id": uid(actor),
                "created_at": now,
                "last_seen_at": now,
                "idle_expires_at": now + timedelta(minutes=20),
                "absolute_expires_at": now + timedelta(hours=8),
                "authentication_time": now,
                "data": {"context": "admin"},
                "version": 0,
                "fixture_version": "synthetic-v1",
            }
        )
        client = app.test_client()
        client.set_cookie(COOKIE, token)
        return client

    admin = browser("administrator")
    response = admin.get("/access")
    assert response.status_code == 200
    csrf = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)[1].decode()
    base = {
        "csrf_token": csrf,
        "operation": "request",
        "target": uid("officer_unassigned"),
        "role": "manager",
        "team": uid("team_finance"),
        "reason": "Synthetic HTTP grant review",
    }
    assert admin.post("/access", data={**base, "global_roles": "administrator"}).status_code == 400
    assert (
        admin.post("/access", data={k: v for k, v in base.items() if k != "csrf_token"}).status_code
        == 400
    )
    assert admin.post("/access", data={**base, "operation": "grant_membership"}).status_code == 403
    assert admin.post("/access", data=base).status_code == 302
    grant = db.privileged_grants.find_one(
        {"user_id": uid("officer_unassigned"), "state": "pending"}
    )
    assert grant
    assert (
        admin.post(
            "/access",
            data={
                "csrf_token": csrf,
                "operation": "approve",
                "grant_id": grant["_id"],
                "reason": "Self approval",
            },
        ).status_code
        == 403
    )
    approver = browser("approver")
    response = approver.get("/access")
    csrf = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)[1].decode()
    assert (
        approver.post(
            "/access",
            data={
                "csrf_token": csrf,
                "operation": "approve",
                "grant_id": grant["_id"],
                "reason": "Independent synthetic approval",
            },
        ).status_code
        == 302
    )
    assert Policy(db, uid("officer_unassigned"), "staff").allows(
        "assign_case", db.cases.find_one({"_id": uid("case_a")})
    )
    db.sessions.delete_many({"user_id": {"$in": [uid("administrator"), uid("approver")]}})
