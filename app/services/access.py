"""Controlled grants and revision-serialized authorization on the real replica set."""

from datetime import timedelta
from uuid import uuid4

from pymongo import ReturnDocument

from app.repositories.core import identifier, plain_text, utc_now
from app.services.audit import AuditWriter
from app.services.policy import AccessDenied, Policy
from app.services.transactions import transaction

PRIVILEGED = {"manager", "administrator", "access_approver", "audit_reviewer"}


class AccessService:
    def __init__(self, database):
        self.db = database

    def transaction(self, operation):
        return transaction(self.db, operation)

    def guard(self, user_id, context, action, case_id, mutation):
        def operation(sid):
            policy = Policy(self.db, user_id, context, sid)
            case = self.db.cases.find_one({"_id": identifier(case_id)}, session=sid)
            policy.require(action, case)
            self.touch_user(user_id, sid)
            # Also serialize current team status/membership and assignment.
            self.db.teams.update_one(
                {"_id": case["team_id"]}, {"$inc": {"authorization_revision": 1}}, session=sid
            )
            self.db.cases.update_one(
                {"_id": case["_id"], "version": case["version"]},
                {"$inc": {"version": 1}},
                session=sid,
            )
            return mutation(sid, case)

        return self.transaction(operation)

    def touch_user(self, user_id, sid):
        self.db.users.update_one(
            {"_id": identifier(user_id)}, {"$inc": {"guard_version": 1}}, session=sid
        )

    def audit(self, actor, action, target_type, target_id, fields, sid):
        AuditWriter(self.db).append(actor, action, target_type, target_id, fields, sid)

    def invalidate(self, user_id, sid):
        self.db.users.update_one(
            {"_id": identifier(user_id)},
            {"$inc": {"authorization_revision": 1, "guard_version": 1}},
            session=sid,
        )
        self.db.sessions.update_many(
            {"user_id": user_id, "revoked_at": None},
            {"$set": {"revoked_at": utc_now()}},
            session=sid,
        )

    def authorize_admin(self, actor, context, action, sid):
        policy = Policy(self.db, actor, context, sid)
        policy.require(action)
        self.touch_user(actor, sid)

    def membership(self, actor, context, target, team, role, active, reason):
        if role not in {"officer", "triage"} or type(active) is not bool:
            raise AccessDenied("Use independent approval for privileged roles.")
        reason = plain_text(reason, 1000)
        identifier(target)
        identifier(team)

        def operation(sid):
            self.authorize_admin(actor, context, "manage_accounts", sid)
            if not self.db.users.find_one(
                {"_id": target}, session=sid
            ) or not self.db.teams.find_one({"_id": team, "active": True}, session=sid):
                raise AccessDenied("Invalid target.")
            self.db.memberships.update_one(
                {"user_id": target, "team_id": team, "role": role},
                {
                    "$set": {
                        "active": active,
                        "granted_by": actor,
                        "granted_at": utc_now(),
                        "revoked_at": None if active else utc_now(),
                    },
                    "$setOnInsert": {"_id": str(uuid4())},
                },
                upsert=True,
                session=sid,
            )
            self.invalidate(target, sid)
            self.audit(actor, "membership_changed", "user", target, ["active", "role"], sid)

        return self.transaction(operation)

    def deactivate(self, actor, context, target, reason):
        plain_text(reason, 1000)
        if target == actor:
            raise AccessDenied("A separate administrator must disable this account.")

        def operation(sid):
            self.authorize_admin(actor, context, "manage_accounts", sid)
            if not self.db.users.update_one(
                {"_id": identifier(target)}, {"$set": {"account_status": "disabled"}}, session=sid
            ).matched_count:
                raise AccessDenied("Invalid target.")
            self.invalidate(target, sid)
            self.audit(actor, "account_disabled", "user", target, ["account_status"], sid)

        return self.transaction(operation)

    def request_grant(self, actor, context, target, role, team, reason):
        if role not in PRIVILEGED:
            raise AccessDenied("Invalid role.")
        reason = plain_text(reason, 1000)
        identifier(target)
        if (role in {"manager", "audit_reviewer"}) != bool(team):
            raise AccessDenied("Explicit team scope required.")
        grant_id = str(uuid4())

        def operation(sid):
            self.authorize_admin(actor, context, "request_grant", sid)
            if not self.db.users.find_one({"_id": target, "account_status": "active"}, session=sid):
                raise AccessDenied("Invalid target.")
            if team and not self.db.teams.find_one(
                {"_id": identifier(team), "active": True}, session=sid
            ):
                raise AccessDenied("Invalid team.")
            doc = {
                "_id": grant_id,
                "user_id": target,
                "role": role,
                "requested_by": actor,
                "reason": reason,
                "state": "pending",
                "created_at": utc_now(),
            }
            if team:
                doc["team_id"] = team
            self.db.privileged_grants.insert_one(doc, session=sid)
            self.audit(actor, "grant_requested", "privileged_grant", grant_id, ["state"], sid)
            return grant_id

        return self.transaction(operation)

    def approve(self, actor, context, grant_id, reason):
        reason = plain_text(reason, 1000)

        def operation(sid):
            self.authorize_admin(actor, context, "approve_grant", sid)
            grant = self.db.privileged_grants.find_one(
                {"_id": identifier(grant_id), "state": "pending"}, session=sid
            )
            if not grant or actor in {grant["requested_by"], grant["user_id"]}:
                raise AccessDenied("Independent approval required.")
            target = grant["user_id"]
            if not self.db.users.find_one({"_id": target, "account_status": "active"}, session=sid):
                raise AccessDenied("Account unavailable.")
            if grant.get("team_id") and not self.db.teams.find_one(
                {"_id": grant["team_id"], "active": True}, session=sid
            ):
                raise AccessDenied("Team unavailable.")
            if grant["role"] == "manager":
                self.db.memberships.update_one(
                    {"user_id": target, "team_id": grant["team_id"], "role": "manager"},
                    {
                        "$set": {
                            "active": True,
                            "granted_by": actor,
                            "granted_at": utc_now(),
                            "revoked_at": None,
                        },
                        "$setOnInsert": {"_id": str(uuid4())},
                    },
                    upsert=True,
                    session=sid,
                )
            else:
                self.db.users.update_one(
                    {"_id": target}, {"$addToSet": {"global_roles": grant["role"]}}, session=sid
                )
            self.db.privileged_grants.update_one(
                {"_id": grant_id, "state": "pending"},
                {
                    "$set": {
                        "state": "approved",
                        "approved_by": actor,
                        "decided_at": utc_now(),
                        "decision_reason": reason,
                    }
                },
                session=sid,
            )
            self.invalidate(target, sid)
            self.audit(actor, "grant_approved", "privileged_grant", grant_id, ["state"], sid)

        return self.transaction(operation)

    def claim(self, user_id, context, case_id):
        def mutation(sid, case):
            now = utc_now()
            old = self.db.triage_claims.find_one({"case_id": case_id}, session=sid)
            if old and old["state"] == "active" and old["expires_at"] > now:
                if old["user_id"] != user_id:
                    raise AccessDenied("Already claimed.")
                return old["_id"]
            doc = {
                "user_id": user_id,
                "team_id": case["team_id"],
                "created_at": now,
                "expires_at": now + timedelta(minutes=30),
                "state": "active",
                "authorization_revision": self.db.users.find_one({"_id": user_id}, session=sid)[
                    "authorization_revision"
                ],
            }
            record = self.db.triage_claims.find_one_and_update(
                {"case_id": case_id},
                {"$set": doc, "$inc": {"version": 1}, "$setOnInsert": {"_id": str(uuid4())}},
                upsert=True,
                return_document=ReturnDocument.AFTER,
                session=sid,
            )
            self.audit(user_id, "triage_claimed", "case", case_id, ["claim"], sid)
            return record["_id"]

        return self.guard(user_id, context, "claim_triage", case_id, mutation)

    def revoke(self, actor, context, target, role, team, reason):
        plain_text(reason, 1000)
        if role not in PRIVILEGED:
            raise AccessDenied("Invalid role.")
        if target == actor:
            raise AccessDenied("A separate administrator must revoke this access.")
        if (role in {"manager", "audit_reviewer"}) != bool(team):
            raise AccessDenied("Explicit scope required.")

        def operation(sid):
            self.authorize_admin(actor, context, "manage_accounts", sid)
            identifier(target)
            if role == "manager":
                self.db.memberships.update_one(
                    {"user_id": target, "team_id": identifier(team), "role": role},
                    {"$set": {"active": False, "revoked_at": utc_now()}},
                    session=sid,
                )
            query = {"user_id": target, "role": role, "state": "approved"}
            if team:
                query["team_id"] = identifier(team)
            self.db.privileged_grants.update_many(
                query,
                {"$set": {"state": "revoked", "decided_at": utc_now(), "decision_reason": reason}},
                session=sid,
            )
            if role != "manager" and not (
                role == "audit_reviewer"
                and self.db.privileged_grants.find_one(
                    {"user_id": target, "role": role, "state": "approved"}, session=sid
                )
            ):
                self.db.users.update_one(
                    {"_id": target}, {"$pull": {"global_roles": role}}, session=sid
                )
            self.invalidate(target, sid)
            self.audit(actor, "privilege_revoked", "user", target, ["role"], sid)

        return self.transaction(operation)
