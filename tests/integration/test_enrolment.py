import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest

from app.repositories.core import utc_now
from app.services.accounts import Accounts
from app.services.enrolment import Enrolment, invitation_hash
from app.services.policy import AccessDenied

pytestmark = [
    pytest.mark.runtime,
    pytest.mark.skipif(os.getenv("RUN_RUNTIME") != "1", reason="Local replica set"),
]
SETTINGS = {
    "IDENTITY_FINGERPRINT_KEY": "invitation-test-identity-key-" * 3,
    "ENROLMENT_MODE": "invitation",
}
ISSUER = "https://university-id.example.invalid/realms/university"


def test_invitation_requires_matching_verified_contact_and_confers_only_approved_role(bundle):
    db, uid = bundle
    enrol = Enrolment(db)
    email = "invite-" + uuid4().hex + "@example.invalid"
    subject = uuid4().hex
    row, token = enrol.create(
        uid("administrator"), "admin", ISSUER, email, "officer", uid("team_finance")
    )
    assert "token" not in row and token not in str(row)
    claims = {
        "sub": subject,
        "name": "Invited officer",
        "email": email,
        "email_verified": True,
        "roles": ["administrator"],
    }
    svc = Accounts(db, SETTINGS)
    for invalid in [
        {**claims, "email_verified": False},
        {**claims, "email": "other@example.invalid"},
    ]:
        with pytest.raises(AccessDenied):
            svc.resolve(ISSUER, invalid, invitation_hash=invitation_hash(token))
    with pytest.raises(AccessDenied):
        enrol.create(uid("student_a"), "student", ISSUER, email, "student")
    with pytest.raises(ValueError):
        enrol.create(uid("administrator"), "admin", ISSUER, email, "manager", uid("team_finance"))
    try:
        user = svc.resolve(ISSUER, claims, invitation_hash=invitation_hash(token))
        assert user["global_roles"] == [] and user["verified_contact"] == email
        member = db.memberships.find_one({"user_id": user["_id"]})
        assert member["role"] == "officer" and member["team_id"] == uid("team_finance")
        with pytest.raises(AccessDenied):
            svc.resolve(ISSUER, claims, invitation_hash=invitation_hash(token))
        assert svc.resolve(ISSUER, claims)["_id"] == user["_id"]
        assert db.enrolment_invitations.find_one({"_id": row["_id"]})["state"] == "accepted"
    finally:
        found = [u["_id"] for u in db.users.find({"identity_subject": subject}, {"_id": 1})]
        db.memberships.delete_many({"user_id": {"$in": found}})
        db.audit_events.delete_many({"actor_id": {"$in": found}})
        db.users.delete_many({"_id": {"$in": found}})


def test_expiry_revocation_and_disabled_inviter_fail_closed(bundle):
    db, uid = bundle
    enrol = Enrolment(db)
    claims = {
        "sub": uuid4().hex,
        "name": "Not enrolled",
        "email": "pending@example.invalid",
        "email_verified": True,
    }
    row, token = enrol.create(uid("administrator"), "admin", ISSUER, claims["email"], "student")
    db.enrolment_invitations.update_one(
        {"_id": row["_id"]}, {"$set": {"expires_at": utc_now() - timedelta(seconds=1)}}
    )
    with pytest.raises(AccessDenied):
        Accounts(db, SETTINGS).resolve(ISSUER, claims, invitation_hash=invitation_hash(token))
    _, token = enrol.create(uid("administrator"), "admin", ISSUER, claims["email"], "student")
    db.users.update_one({"_id": uid("administrator")}, {"$set": {"account_status": "disabled"}})
    with pytest.raises(AccessDenied):
        Accounts(db, SETTINGS).resolve(ISSUER, claims, invitation_hash=invitation_hash(token))
    assert not db.users.find_one({"identity_subject": claims["sub"]})


def test_competing_acceptance_creates_one_account_and_one_membership(bundle):
    db, uid = bundle
    email = uuid4().hex + "@example.invalid"
    subject = uuid4().hex
    row, token = Enrolment(db).create(
        uid("administrator"), "admin", ISSUER, email, "triage", uid("team_finance")
    )
    claims = {"sub": subject, "email": email, "email_verified": True}

    def accept(_):
        try:
            return Accounts(db, SETTINGS).resolve(
                ISSUER, claims, invitation_hash=invitation_hash(token)
            )["_id"]
        except AccessDenied:
            return "denied"

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(accept, range(2)))
        users = list(db.users.find({"identity_subject": subject}, {"_id": 1}))
        assert len(users) == 1 and db.memberships.count_documents({"user_id": users[0]["_id"]}) == 1
        assert any(r != "denied" for r in results)
    finally:
        found = [u["_id"] for u in db.users.find({"identity_subject": subject}, {"_id": 1})]
        db.memberships.delete_many({"user_id": {"$in": found}})
        db.audit_events.delete_many({"actor_id": {"$in": found}})
        db.users.delete_many({"_id": {"$in": found}})
