"""Own-account closure, profile erasure and replayable privacy-review records."""

import hashlib
import hmac
import json
from datetime import timedelta
from uuid import uuid4

from flask import current_app, has_app_context

from app.repositories.core import identifier, utc_now
from app.services.access import AccessService
from app.services.audit import AuditWriter
from app.services.policy import AccessDenied, Policy
from app.services.transactions import VersionConflict, transaction


def fingerprint(issuer, subject, key):
    if not isinstance(key, str) or len(key) < 48:
        raise ValueError("A stable identity-protection key is required.")
    return hmac.new(
        key.encode(), json.dumps([issuer, subject], separators=(",", ":")).encode(), hashlib.sha256
    ).hexdigest()


def redact_principal(db, record, sid):
    """Also used during quarantine restore; no current identity/contact is retained."""
    now = record["requested_at"]
    db.users.update_one(
        {"_id": record["user_id"]},
        {
            "$set": {
                "identity_issuer": "urn:student-support:closed",
                "identity_subject": record["user_id"],
                "identity_fingerprint": record["identity_fingerprint"],
                "display_name": "Closed account",
                "account_status": "closed",
                "global_roles": [],
                "closed_at": now,
            },
            "$unset": {"course_label": "", "student_reference": "", "verified_contact": ""},
            "$inc": {"authorization_revision": 1, "guard_version": 1},
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
        session=sid,
    )
    db.memberships.update_many(
        {"user_id": record["user_id"], "active": True},
        {"$set": {"active": False, "revoked_at": now}},
        session=sid,
    )
    db.sessions.delete_many({"user_id": record["user_id"]}, session=sid)
    db.auth_attempts.delete_many({"data.reauth_user": record["user_id"]}, session=sid)
    db.submission_keys.delete_many({"user_id": record["user_id"]}, session=sid)
    db.triage_claims.update_many(
        {"user_id": record["user_id"], "state": "active"},
        {"$set": {"state": "released"}},
        session=sid,
    )
    db.notification_outbox.update_many(
        {"recipient_user_id": record["user_id"], "state": {"$in": ["pending", "leased"]}},
        {"$set": {"state": "dead"}, "$unset": {"lease_hash": "", "lease_until": ""}},
        session=sid,
    )


class AccountPrivacy:
    def __init__(self, database, identity_key, settings=None):
        self.db = database
        self.key = identity_key
        self.settings = (
            settings if settings is not None else (current_app.config if has_app_context() else {})
        )

    def close(self, actor, version, reauthenticated_at):
        now = utc_now()
        if (
            type(reauthenticated_at) is not int
            or not 0 <= now.timestamp() - reauthenticated_at <= 300
        ):
            raise AccessDenied("Sign in again to confirm account deletion.")
        request_id = str(uuid4())

        def operation(sid):
            user = self.db.users.find_one({"_id": identifier(actor)}, session=sid)
            if not user or user["account_status"] != "active":
                raise AccessDenied("Account unavailable.")
            if type(version) is not int or user.get("profile_version", 0) != version:
                raise VersionConflict("Your profile changed; review it before closing.")
            # Privileged ownership must be transferred rather than losing the only
            # operating administrator/approver. A separate operator manages staff closure.
            if set(user["global_roles"]) - {"student"} or self.db.memberships.find_one(
                {"user_id": actor, "active": True}, session=sid
            ):
                raise AccessDenied(
                    "Staff access must be transferred/revoked before self-service closure."
                )
            related = self.db.cases.find_one({"student_id": actor}, {"_id": 1}, session=sid)
            for name, field in [
                ("messages", "author_id"),
                ("internal_notes", "author_id"),
                ("case_events", "actor_id"),
                ("referrals", "requested_by"),
            ]:
                related = related or self.db[name].find_one({field: actor}, {"_id": 1}, session=sid)
            record = {
                "_id": request_id,
                "user_id": actor,
                "identity_fingerprint": fingerprint(
                    user["identity_issuer"], user["identity_subject"], self.key
                ),
                "state": "review_required" if related else "profile_erased",
                "requested_at": now,
                "review_due_at": now
                + timedelta(days=self.settings.get("ACCOUNT_PRIVACY_REVIEW_DAYS", 30)),
            }
            self.db.account_closures.insert_one(record, session=sid)
            redact_principal(self.db, record, sid)
            AuditWriter(self.db).append(
                actor, "account_closed", "user", actor, ["account_status"], sid
            )
            return record

        return transaction(self.db, operation)

    def review(self, actor, context):
        def read(sid):
            Policy(self.db, actor, context, sid).require("manage_accounts")
            AuditWriter(self.db).append(actor, "privacy_review", "user", actor, [], sid)
            return list(
                self.db.account_closures.find(
                    {},
                    {
                        "user_id": 1,
                        "state": 1,
                        "requested_at": 1,
                        "retention_reason": 1,
                        "review_due_at": 1,
                        "policy_reference": 1,
                    },
                    session=sid,
                )
                .sort([("requested_at", -1), ("_id", -1)])
                .limit(100)
            )

        return transaction(self.db, read)

    def record_retention(self, actor, context, request_id, reason, policy_reference, days):
        from app.repositories.core import plain_text

        reason = plain_text(reason, 1000)
        policy_reference = plain_text(policy_reference, 200)
        if type(days) is not int or not 1 <= days <= 366:
            raise ValueError("Choose a review interval between 1 and 366 days.")

        def operation(sid):
            Policy(self.db, actor, context, sid).require("manage_accounts")
            AccessService(self.db).touch_user(actor, sid)
            row = self.db.account_closures.find_one({"_id": identifier(request_id)}, session=sid)
            if not row or actor == row["user_id"]:
                raise AccessDenied("Independent review required.")
            self.db.account_closures.update_one(
                {"_id": row["_id"]},
                {
                    "$set": {
                        "state": "retained",
                        "retention_reason": reason,
                        "policy_reference": policy_reference,
                        "reviewed_by": actor,
                        "review_due_at": utc_now() + timedelta(days=days),
                    }
                },
                session=sid,
            )
            AuditWriter(self.db).append(actor, "privacy_reviewed", "user", row["user_id"], [], sid)

        transaction(self.db, operation)
