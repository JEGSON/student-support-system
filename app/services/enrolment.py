"""University-issued invitations bound to a verified OIDC identity and email."""

import hashlib
import re
import secrets
from datetime import timedelta
from uuid import uuid4

from app.repositories.core import identifier, plain_text, utc_now
from app.services.access import AccessService
from app.services.audit import AuditWriter
from app.services.policy import AccessDenied, Policy
from app.services.transactions import transaction


def contact_address(value):
    if not isinstance(value, str) or not 3 <= len(value) <= 254 or value != value.strip():
        raise ValueError("Enter a valid email address.")
    if value.count("@") != 1 or any(ord(c) < 33 or ord(c) > 126 for c in value):
        raise ValueError("Enter a valid email address.")
    local, domain = value.rsplit("@", 1)
    if (
        not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}", local)
        or local.startswith(".")
        or local.endswith(".")
        or ".." in local
    ):
        raise ValueError("Enter a valid email address.")
    labels = domain.split(".")
    if len(labels) < 2 or any(
        not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
        for label in labels
    ):
        raise ValueError("Enter a valid email address.")
    return value.casefold()


def invitation_hash(token):
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise ValueError("Enter the complete invitation code.")
    return hashlib.sha256(token.encode()).hexdigest()


class Enrolment:
    def __init__(self, database):
        self.db = database

    def create(self, actor, context, issuer, email, role, team=None):
        email = contact_address(email)
        if role not in {"student", "officer", "triage"} or (role != "student") != bool(team):
            raise ValueError(
                "Choose an ordinary student or team role; privileged roles need separate approval."
            )
        token = secrets.token_urlsafe(32)
        key = str(uuid4())

        def operation(sid):
            Policy(self.db, actor, context, sid).require("manage_accounts")
            AccessService(self.db).touch_user(actor, sid)
            row = {
                "_id": key,
                "token_hash": invitation_hash(token),
                "email": email,
                "issuer": plain_text(issuer, 500),
                "role": role,
                "created_by": actor,
                "state": "pending",
                "created_at": utc_now(),
                "expires_at": utc_now() + timedelta(hours=24),
            }
            if team:
                row["team_id"] = identifier(team)
                if not self.db.teams.find_one({"_id": team, "active": True}, session=sid):
                    raise ValueError("Choose an active team.")
                self.db.teams.update_one(
                    {"_id": team}, {"$inc": {"authorization_revision": 1}}, session=sid
                )
            self.db.enrolment_invitations.insert_one(row, session=sid)
            AuditWriter(self.db).append(actor, "invitation_created", "user", actor, [], sid)
            return row

        row = transaction(self.db, operation)
        return row, token

    def pending(self, token_hash, issuer, claims, sid):
        if claims.get("email_verified") is not True:
            raise AccessDenied("Verify your email with the account service first.")
        email = contact_address(claims.get("email"))
        row = self.db.enrolment_invitations.find_one(
            {
                "token_hash": token_hash,
                "issuer": issuer,
                "email": email,
                "state": "pending",
                "expires_at": {"$gt": utc_now()},
            },
            session=sid,
        )
        if not row:
            raise AccessDenied("Invitation unavailable or does not match this verified identity.")
        Policy(self.db, row["created_by"], "admin", sid).require("manage_accounts")
        AccessService(self.db).touch_user(row["created_by"], sid)
        if row.get("team_id"):
            if not self.db.teams.find_one({"_id": row["team_id"], "active": True}, session=sid):
                raise AccessDenied("Team unavailable.")
            self.db.teams.update_one(
                {"_id": row["team_id"]}, {"$inc": {"authorization_revision": 1}}, session=sid
            )
        return row

    def accept(self, row, user, sid, *, new_account):
        # Existing account access is changed through the established administrator
        # workflow, so an old invitation cannot restore a subsequently revoked role.
        if new_account and row["role"] != "student":
            now = utc_now()
            self.db.memberships.insert_one(
                {
                    "_id": str(uuid4()),
                    "user_id": user["_id"],
                    "team_id": row["team_id"],
                    "role": row["role"],
                    "active": True,
                    "granted_by": row["created_by"],
                    "granted_at": now,
                },
                session=sid,
            )
        self.db.enrolment_invitations.update_one(
            {"_id": row["_id"], "state": "pending"},
            {"$set": {"state": "accepted", "accepted_by": user["_id"], "accepted_at": utc_now()}},
            session=sid,
        )
        AuditWriter(self.db).append(
            user["_id"], "invitation_accepted", "user", user["_id"], [], sid
        )

    def list(self, actor, context):
        Policy(self.db, actor, context).require("manage_accounts")
        return list(
            self.db.enrolment_invitations.find({}, {"token_hash": 0})
            .sort([("created_at", -1), ("_id", -1)])
            .limit(100)
        )

    def revoke(self, actor, context, key):
        def operation(sid):
            Policy(self.db, actor, context, sid).require("manage_accounts")
            AccessService(self.db).touch_user(actor, sid)
            if not self.db.enrolment_invitations.update_one(
                {"_id": identifier(key), "state": "pending"},
                {"$set": {"state": "revoked"}},
                session=sid,
            ).matched_count:
                raise ValueError("Invitation unavailable.")
            AuditWriter(self.db).append(actor, "invitation_revoked", "user", actor, [], sid)

        transaction(self.db, operation)
