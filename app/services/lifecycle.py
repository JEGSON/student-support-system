"""Explicit synthetic retention; no institution policy or automatic case TTL."""

from datetime import timedelta
from uuid import uuid4

from app.repositories.core import identifier, plain_text, utc_now
from app.services.access import AccessService
from app.services.audit import AuditWriter
from app.services.policy import AccessDenied, Policy
from app.services.transactions import VersionConflict, transaction

POLICY = "synthetic-demo-1day"


class Lifecycle:
    def __init__(self, database):
        self.db = database

    def require_synthetic(self, policy):
        if policy != POLICY or self.db.name not in {"student_support_dev", "student_support_test"}:
            raise AccessDenied("Real retention is unconfigured; synthetic local policy only.")

    def reassignment(self, actor, context):
        def read(sid):
            policy = Policy(self.db, actor, context, sid)
            teams = [
                m["team_id"]
                for m in self.db.memberships.find(
                    {"user_id": actor, "active": True, "role": "manager"}, session=sid
                )
                if policy.membership(m["team_id"], {"manager"})
            ]
            rows = list(
                self.db.cases.find(
                    {
                        "team_id": {"$in": teams},
                        "archive_state": "active",
                        "status": {"$ne": "Closed"},
                    },
                    {"reference": 1, "team_id": 1, "assignee_id": 1, "status": 1},
                    session=sid,
                    max_time_ms=1500,
                ).limit(100)
            )
            result = []
            for case in rows:
                assignee = case["assignee_id"]
                eligible = (
                    assignee
                    and self.db.users.find_one(
                        {"_id": assignee, "account_status": "active"}, session=sid
                    )
                    and self.db.memberships.find_one(
                        {
                            "user_id": assignee,
                            "team_id": case["team_id"],
                            "active": True,
                            "role": {"$in": ["officer", "manager"]},
                        },
                        session=sid,
                    )
                )
                if not eligible:
                    result.append(case)
            AuditWriter(self.db).append(actor, "reassignment_review", "user", actor, [], sid)
            return result

        return transaction(self.db, read)

    def archive(self, actor, context, case_id, version):
        def write(sid, case):
            if case["version"] != version:
                raise VersionConflict("Request changed.")
            if case["status"] != "Closed":
                raise AccessDenied("Only closed cases may be archived.")
            self.db.cases.update_one(
                {"_id": case_id}, {"$set": {"archive_state": "archived"}}, session=sid
            )
            AuditWriter(self.db).append(
                actor, "case_archived", "case", case_id, ["archive_state"], sid
            )

        return AccessService(self.db).guard(actor, context, "assign_case", case_id, write)

    def archive_read(self, actor, context, case_id, purpose):
        plain_text(purpose, 1000)

        def read(sid):
            policy = Policy(self.db, actor, context, sid)
            case = self.db.cases.find_one(
                {"_id": identifier(case_id), "archive_state": "archived"}, session=sid
            )
            if not case or not policy.membership(case["team_id"], {"manager"}):
                raise AccessDenied("Scoped archived access required.")
            AccessService(self.db).touch_user(actor, sid)
            AuditWriter(self.db).append(actor, "archive_read", "case", case_id, [], sid)
            return {
                key: case[key]
                for key in ["reference", "description", "status", "created_at", "_id"]
            }

        return transaction(self.db, read)

    def review(self, actor, context):
        def read(sid):
            policy = Policy(self.db, actor, context, sid)
            if not (policy.allows("manage_accounts") or policy.allows("approve_grant")):
                raise AccessDenied("Retention metadata access denied.")
            rows = list(
                self.db.cases.find(
                    {"archive_state": "archived", "status": "Closed"},
                    {"reference": 1, "closed_at": 1, "legal_hold": 1, "status": 1},
                    session=sid,
                    max_time_ms=1500,
                ).limit(100)
            )
            ledger = list(
                self.db.disposal_records.find({}, session=sid, max_time_ms=1500)
                .sort("created_at", -1)
                .limit(100)
            )
            AuditWriter(self.db).append(actor, "retention_review", "user", actor, [], sid)
            return rows, ledger

        return transaction(self.db, read)

    def hold(self, actor, context, case_id, enabled, reason):
        plain_text(reason, 1000)
        if type(enabled) is not bool:
            raise ValueError("Invalid hold.")

        def write(sid):
            AccessService(self.db).authorize_admin(actor, context, "manage_accounts", sid)
            if not self.db.cases.update_one(
                {"_id": identifier(case_id)},
                {"$set": {"legal_hold": enabled}, "$inc": {"version": 1}},
                session=sid,
            ).matched_count:
                raise AccessDenied("Case unavailable.")
            AuditWriter(self.db).append(actor, "hold_changed", "case", case_id, ["legal_hold"], sid)

        transaction(self.db, write)

    def request(self, actor, context, case_id, policy, reason):
        self.require_synthetic(policy)
        reason = plain_text(reason, 1000)

        def write(sid):
            AccessService(self.db).authorize_admin(actor, context, "manage_accounts", sid)
            self.eligible(case_id, sid)
            existing = self.db.disposal_records.find_one({"case_id": case_id}, session=sid)
            if existing:
                return existing["_id"]
            row = {
                "_id": str(uuid4()),
                "case_id": identifier(case_id),
                "requested_by": actor,
                "policy": POLICY,
                "reason": reason,
                "state": "pending",
                "created_at": utc_now(),
            }
            self.db.disposal_records.insert_one(row, session=sid)
            AuditWriter(self.db).append(actor, "disposal_requested", "case", case_id, [], sid)
            return row["_id"]

        return transaction(self.db, write)

    def approve(self, actor, context, record_id):
        def write(sid):
            AccessService(self.db).authorize_admin(actor, context, "approve_grant", sid)
            row = self.db.disposal_records.find_one(
                {"_id": identifier(record_id), "state": "pending"}, session=sid
            )
            if not row or row["requested_by"] == actor:
                raise AccessDenied("Separate approval required.")
            self.require_synthetic(row["policy"])
            self.eligible(row["case_id"], sid)
            self.db.disposal_records.update_one(
                {"_id": record_id},
                {"$set": {"approved_by": actor, "state": "approved"}},
                session=sid,
            )
            AuditWriter(self.db).append(actor, "disposal_approved", "case", row["case_id"], [], sid)

        transaction(self.db, write)

    def eligible(self, case_id, sid):
        case = self.db.cases.find_one(
            {
                "_id": identifier(case_id),
                "status": "Closed",
                "archive_state": "archived",
                "legal_hold": False,
                "closed_at": {"$lte": utc_now() - timedelta(days=1)},
            },
            session=sid,
        )
        if not case:
            raise AccessDenied("Not eligible under the synthetic one-day policy, or held.")
        return case

    def execute(self, record_id):
        # Called only by the offline maintenance CLI. Web DB roles cannot delete
        # case history or the ledger. Replaying a completed record is harmless.
        def write(sid):
            row = self.db.disposal_records.find_one({"_id": identifier(record_id)}, session=sid)
            if not row:
                raise AccessDenied("Disposal record unavailable.")
            self.require_synthetic(row["policy"])
            if row["state"] == "completed":
                return
            if row["state"] != "approved" or row["approved_by"] == row["requested_by"]:
                raise AccessDenied("Approved disposal required.")
            Policy(self.db, row["requested_by"], "admin", sid).require("manage_accounts")
            Policy(self.db, row["approved_by"], "admin", sid).require("approve_grant")
            AccessService(self.db).touch_user(row["requested_by"], sid)
            AccessService(self.db).touch_user(row["approved_by"], sid)
            self.eligible(row["case_id"], sid)
            erase_linked(self.db, row["case_id"], sid)
            self.db.disposal_records.update_one(
                {"_id": record_id},
                {"$set": {"state": "completed", "completed_at": utc_now()}},
                session=sid,
            )
            AuditWriter(self.db).append(
                row["approved_by"], "case_disposed", "case", row["case_id"], [], sid
            )

        transaction(self.db, write)


def erase_linked(db, case_id, sid):
    message_ids = [
        r["_id"] for r in db.messages.find({"case_id": case_id}, {"_id": 1}, session=sid)
    ]
    refs = [
        r["_id"]
        for r in db.referrals.find(
            {"$or": [{"source_case_id": case_id}, {"target_case_id": case_id}]},
            {"_id": 1},
            session=sid,
        )
    ]
    db.cases.update_many(
        {"originating_referral_id": {"$in": refs}},
        {"$unset": {"originating_referral_id": ""}},
        session=sid,
    )
    db.referrals.delete_many({"_id": {"$in": refs}}, session=sid)
    for collection in [
        "messages",
        "internal_notes",
        "case_events",
        "notification_outbox",
        "triage_claims",
    ]:
        db[collection].delete_many({"case_id": case_id}, session=sid)
    db.submission_keys.delete_many({"result_id": {"$in": [case_id, *message_ids]}}, session=sid)
    db.cases.delete_one({"_id": case_id}, session=sid)
