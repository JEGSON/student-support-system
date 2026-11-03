"""Explicit operator bootstrap for a university service, never a public endpoint."""

from uuid import NAMESPACE_URL, uuid4, uuid5

from app.repositories.core import plain_text, utc_now
from app.services.audit import AuditWriter
from app.services.enrolment import contact_address
from app.services.policy import AccessDenied
from app.services.transactions import transaction


def bootstrap_service(database, issuer, administrator, approver):
    records = []
    for person, role in [(administrator, "administrator"), (approver, "access_approver")]:
        if not isinstance(person, dict) or set(person) != {"subject", "name", "verified_contact"}:
            raise ValueError(
                "Supply exactly subject, name and verified_contact from the approved identity source."
            )
        records.append(
            {
                "_id": str(uuid4()),
                "identity_issuer": issuer,
                "identity_subject": plain_text(person["subject"], 255),
                "display_name": plain_text(person["name"], 160),
                "verified_contact": contact_address(person["verified_contact"]),
                "account_status": "active",
                "global_roles": [role],
                "authorization_revision": 0,
                "created_at": utc_now(),
            }
        )
    if (
        records[0]["identity_subject"] == records[1]["identity_subject"]
        or records[0]["verified_contact"] == records[1]["verified_contact"]
    ):
        raise ValueError("Two independent university identities are required.")
    guard = str(uuid5(NAMESPACE_URL, "student-support/bootstrap/" + database.name))

    def operation(sid):
        database.service_principals.update_one(
            {"_id": guard},
            {
                "$setOnInsert": {
                    "name": "University bootstrap guard",
                    "kind": "bootstrap_guard",
                    "active": False,
                },
                "$inc": {"authorization_revision": 1},
            },
            upsert=True,
            session=sid,
        )
        if database.users.find_one(
            {"global_roles": {"$in": ["administrator", "access_approver"]}}, {"_id": 1}, session=sid
        ):
            raise AccessDenied(
                "Privileged access already exists; use the controlled administration workflow."
            )
        for record in records:
            if database.users.find_one(
                {"identity_issuer": issuer, "identity_subject": record["identity_subject"]},
                {"_id": 1},
                session=sid,
            ):
                raise AccessDenied(
                    "An identity is already enrolled; use a reviewed operator migration."
                )
            database.users.insert_one(record, session=sid)
        for user, other in [(records[0], records[1]), (records[1], records[0])]:
            database.privileged_grants.insert_one(
                {
                    "_id": str(uuid4()),
                    "user_id": user["_id"],
                    "role": user["global_roles"][0],
                    "requested_by": user["_id"],
                    "approved_by": other["_id"],
                    "reason": "Operator-attested initial university bootstrap",
                    "decision_reason": "Independent identity supplied through trusted operator setup",
                    "state": "approved",
                    "created_at": utc_now(),
                    "decided_at": utc_now(),
                },
                session=sid,
            )
            AuditWriter(database).append(
                other["_id"], "service_bootstrapped", "user", user["_id"], ["global_roles"], sid
            )
        principal = str(uuid4())
        database.service_principals.insert_one(
            {
                "_id": principal,
                "name": "University notification worker",
                "kind": "notification_worker",
                "active": True,
                "authorization_revision": 0,
            },
            session=sid,
        )
        return {
            "administrator_id": records[0]["_id"],
            "approver_id": records[1]["_id"],
            "notification_principal_id": principal,
        }

    return transaction(database, operation)
