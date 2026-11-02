"""Append-only safe audit metadata and an explicit scoped reader."""

import re
from uuid import uuid4

from flask import g, has_request_context
from pymongo.write_concern import WriteConcern

from app.repositories.core import identifier, utc_now
from app.services.policy import Policy
from app.services.transactions import transaction

ACTIONS = {
    "reassignment_review",
    "case_archived",
    "archive_read",
    "retention_review",
    "hold_changed",
    "disposal_requested",
    "disposal_approved",
    "case_disposed",
    "referrals_read",
    "referral_changed",
    "messages_read",
    "notes_read",
    "communication_changed",
    "staff_queue",
    "triage_read",
    "triage_released",
    "membership_changed",
    "account_disabled",
    "grant_requested",
    "grant_approved",
    "triage_claimed",
    "privilege_revoked",
    "offline_synthetic_bootstrap",
    "case_read",
    "cases_listed",
    "case_submitted",
    "case_changed",
    "audit_reviewed",
}
TARGETS = {"user", "case", "privileged_grant"}
FIELDS = {
    "legal_hold",
    "body",
    "active",
    "role",
    "account_status",
    "state",
    "claim",
    "global_roles",
    "category",
    "description",
    "team_id",
    "assignee_id",
    "status",
    "priority",
    "priority_reason",
    "version",
    "archive_state",
}


class AuditWriter:
    def __init__(self, database):
        self.db = database

    def append(self, actor, action, target_type, target_id, fields, sid=None, request_id=None):
        if action not in ACTIONS or target_type not in TARGETS or not set(fields) <= FIELDS:
            raise ValueError("Invalid audit metadata.")
        request_id = request_id or (
            g.request_id if has_request_context() and hasattr(g, "request_id") else str(uuid4())
        )
        if not isinstance(request_id, str) or not re.fullmatch(r"[0-9a-f-]{36}", request_id):
            raise ValueError("Invalid correlation identifier.")
        doc = {
            "_id": str(uuid4()),
            "actor_id": identifier(actor),
            "action": action,
            "target_type": target_type,
            "target_id": identifier(target_id),
            "outcome": "allowed",
            "occurred_at": utc_now(),
            "request_id": request_id,
            "changed_field_names": sorted(set(fields)),
        }
        collection = self.db.audit_events
        if sid is None:
            collection = collection.with_options(
                write_concern=WriteConcern("majority", wtimeout=1500)
            )
        collection.insert_one(doc, session=sid)


class AuditReader:
    """The separate read credential is never loaded by the public Flask process."""

    def __init__(self, web_database, audit_database):
        self.db = web_database
        self.reader = audit_database

    def for_case(self, actor, context, case_id, purpose, limit=50):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Invalid limit.")

        def authorise(sid):
            policy = Policy(self.db, actor, context, sid)
            case = self.db.cases.find_one({"_id": identifier(case_id)}, session=sid)
            policy.require("read_audit", case, purpose=purpose)
            self.db.users.update_one({"_id": actor}, {"$inc": {"guard_version": 1}}, session=sid)
            AuditWriter(self.db).append(actor, "audit_reviewed", "case", case_id, [], sid)

        transaction(self.db, authorise)
        return list(
            self.reader.audit_events.find(
                {"target_type": "case", "target_id": case_id},
                {
                    "_id": 0,
                    "action": 1,
                    "actor_id": 1,
                    "service_id": 1,
                    "occurred_at": 1,
                    "request_id": 1,
                    "changed_field_names": 1,
                    "outcome": 1,
                },
                max_time_ms=1500,
            )
            .sort([("occurred_at", -1), ("_id", -1)])
            .limit(limit)
        )
