"""Student-only services: scoped queries, safe projections and audited reads."""

import hashlib
import json
import secrets
from uuid import uuid4

from app.repositories.core import InvalidInput, identifier, utc_now
from app.repositories.schema import CATEGORIES
from app.repositories.student import StudentCaseRepository
from app.services.access import AccessService
from app.services.audit import AuditWriter
from app.services.outbox import Outbox
from app.services.policy import Policy
from app.services.references import validate_references
from app.services.submissions import idempotent
from app.services.transactions import transaction


class RoutingUnavailable(RuntimeError):
    pass


def normalize_description(value):
    return value.replace("\r\n", "\n").replace("\r", "\n") if isinstance(value, str) else value


def validate_submission(category, description):
    description = normalize_description(description)
    errors = {}
    if not isinstance(category, str) or category not in CATEGORIES:
        errors["category"] = "Choose a support area."
    if not isinstance(description, str) or not description.strip():
        errors["description"] = "Tell us what you need support with."
    elif len(description) > 10000:
        errors["description"] = "Use 10,000 characters or fewer."
    elif any(ord(c) < 32 and c not in "\r\n\t" for c in description):
        errors["description"] = "Remove unsupported control characters."
    return errors


def student_view(case, detail=False):
    keys = {"_id", "reference", "category", "status", "created_at", "updated_at"}
    if detail:
        keys.add("description")
    return {key: case[key] for key in keys}


class StudentCases:
    def __init__(self, database, routing, routing_source="environment"):
        self.db = database
        self.routing = routing
        self.routing_source = routing_source
        self.cases = StudentCaseRepository(database)

    def authorise(self, actor, context, sid):
        policy = Policy(self.db, actor, context, sid)
        policy.require("submit_case")
        AccessService(self.db).touch_user(actor, sid)
        return policy

    def create(self, actor, context, category, description, key_hash):
        if validate_submission(category, description):
            raise InvalidInput("Invalid submission.")
        description = normalize_description(description).strip()
        payload = hashlib.sha256(
            json.dumps([category, description], ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
        case_id = str(uuid4())
        reference = "SS-" + secrets.token_hex(8).upper()
        stamp = utc_now()

        def operation(sid):
            self.authorise(actor, context, sid)

            def create():
                intake = self.db.teams.find_one(
                    {"active": True, "routing_categories": category}, {"_id": 1}, session=sid
                )
                team_id = (
                    intake["_id"]
                    if intake
                    else (
                        self.routing.get(category) if self.routing_source == "environment" else None
                    )
                )
                if not team_id:
                    raise RoutingUnavailable("Support routing is unavailable.")
                team = self.db.teams.find_one(
                    {"_id": team_id, "active": True, "category_scope": category}, session=sid
                )
                if not team:
                    raise RoutingUnavailable("Support routing is unavailable.")
                # Serialize team disablement against the submission transaction.
                self.db.teams.update_one(
                    {"_id": team_id}, {"$inc": {"authorization_revision": 1}}, session=sid
                )
                record = {
                    "_id": case_id,
                    "reference": reference,
                    "student_id": actor,
                    "category": category,
                    "description": description,
                    "team_id": team_id,
                    "assignee_id": None,
                    "status": "New",
                    "priority": "standard",
                    "version": 1,
                    "created_at": stamp,
                    "updated_at": stamp,
                    "archive_state": "active",
                    "legal_hold": False,
                }
                validate_references(self.db, "cases", record, session=sid)
                event_id = str(uuid4())
                self.cases.insert(
                    record,
                    {
                        "_id": event_id,
                        "case_id": case_id,
                        "actor_id": actor,
                        "event_type": "submitted",
                        "created_at": stamp,
                    },
                    sid,
                )
                AuditWriter(self.db).append(
                    actor,
                    "case_submitted",
                    "case",
                    case_id,
                    ["category", "description", "team_id", "status"],
                    sid,
                )
                Outbox(self.db).enqueue(sid, event_id, actor, case_id, "case_received")
                return case_id

            return idempotent(self.db, sid, actor, "create_case", key_hash, payload, create)

        return transaction(self.db, operation)

    def list(self, actor, context, after=None):
        def operation(sid):
            self.authorise(actor, context, sid)
            rows = self.cases.page(actor, after, sid)
            AuditWriter(self.db).append(actor, "cases_listed", "user", actor, [], sid)
            return [student_view(row) for row in rows[:20]], (
                rows[19]["updated_at"],
                rows[19]["_id"],
            ) if len(rows) > 20 else None

        return transaction(self.db, operation)

    def detail(self, actor, context, case_id):
        identifier(case_id)

        def operation(sid):
            policy = self.authorise(actor, context, sid)
            case = self.cases.own(actor, case_id, sid)
            policy.require("read_case", case)
            AuditWriter(self.db).append(actor, "case_read", "case", case_id, [], sid)
            return student_view(case, detail=True)

        return transaction(self.db, operation)
