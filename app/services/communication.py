"""Atomic, versioned conversation and lifecycle rules; notes are a separate path."""

import hashlib
import json
from uuid import uuid4

from app.repositories.core import identifier, plain_text, utc_now
from app.services.access import AccessService
from app.services.audit import AuditWriter
from app.services.outbox import Outbox
from app.services.policy import AccessDenied, Policy
from app.services.references import validate_references
from app.services.student_cases import normalize_description, validate_submission
from app.services.submissions import idempotent
from app.services.transactions import VersionConflict, transaction


class Communication:
    def __init__(self, database):
        self.db = database

    def thread(self, actor, context, case_id, *, notes=False, before=None):
        def operation(sid):
            policy = Policy(self.db, actor, context, sid)
            case = self.db.cases.find_one({"_id": identifier(case_id)}, session=sid)
            policy.require("read_notes" if notes else "read_messages", case)
            if notes and context != "staff":
                raise AccessDenied("Internal notes unavailable.")
            query = {"case_id": case_id}
            if before:
                stamp, key = before
                query["$or"] = [
                    {"created_at": {"$lt": stamp}},
                    {"created_at": stamp, "_id": {"$lt": identifier(key)}},
                ]
            collection = self.db.internal_notes if notes else self.db.messages
            docs = list(
                collection.find(query, session=sid, max_time_ms=1500)
                .sort([("created_at", -1), ("_id", -1)])
                .limit(51)
            )
            result = []
            for row in reversed(docs[:50]):
                result.append(
                    {
                        "_id": row["_id"],
                        "body": row["body"],
                        "created_at": row["created_at"],
                        "author": "You"
                        if row["author_id"] == actor
                        else "Student"
                        if row.get("author_context") == "student"
                        else "Support team",
                        "correction": row.get("supersedes_id" if notes else "correction_of"),
                    }
                )
            AccessService(self.db).touch_user(actor, sid)
            AuditWriter(self.db).append(
                actor, "notes_read" if notes else "messages_read", "case", case_id, [], sid
            )
            cursor = (docs[49]["created_at"], docs[49]["_id"]) if len(docs) > 50 else None
            return result, cursor, case["version"]

        return transaction(self.db, operation)

    def act(
        self,
        actor,
        context,
        case_id,
        version,
        operation,
        *,
        body="",
        reason="",
        correction=None,
        key_hash=None,
        assignee=None,
    ):
        actions = {
            "message": "send_message",
            "question": "update_case",
            "note": "write_note",
            "close": "update_case",
            "reopen": "reopen_case",
            "resume": "update_case",
        }
        if operation not in actions:
            raise ValueError("Invalid communication action.")
        if operation not in {"reopen", "resume"}:
            body = normalize_description(body)
            if validate_submission("finance", body):
                raise ValueError("Use 1–10,000 characters of plain text.")
            body = body.strip()
        else:
            reason = plain_text(reason, 1000)
        if correction:
            identifier(correction)
        fingerprint = hashlib.sha256(
            json.dumps([case_id, operation, body, correction], ensure_ascii=False).encode()
        ).hexdigest()

        def operation_tx(sid):
            policy = Policy(self.db, actor, context, sid)
            case = self.db.cases.find_one({"_id": identifier(case_id)}, session=sid)
            policy.require(actions[operation], case)
            AccessService(self.db).touch_user(actor, sid)

            def write():
                if type(version) is not int or case["version"] != version:
                    raise VersionConflict("Request changed. Review it before retrying.")
                if case["status"] == "Closed" and operation != "reopen":
                    raise AccessDenied("A manager must reopen this case.")
                if context != "staff" and operation != "message":
                    raise AccessDenied("Staff action required.")
                now = utc_now()
                changes = {"updated_at": now}
                event = "message_added"
                template = "case_updated"
                collection = "internal_notes" if operation == "note" else "messages"
                message_id = str(uuid4())
                if operation == "question":
                    if case["status"] != "In Progress":
                        raise AccessDenied("Questions require In Progress.")
                    changes["status"] = "Awaiting Student"
                    event = "information_requested"
                    template = "information_requested"
                elif operation == "close":
                    if case["status"] != "In Progress":
                        raise AccessDenied("Closure requires In Progress and an outcome.")
                    changes.update(status="Closed", closed_at=now, resolution_message_id=message_id)
                    event = "closed"
                    template = "case_closed"
                elif operation == "reopen":
                    if case["status"] != "Closed":
                        raise AccessDenied("Only Closed requests can reopen.")
                    changes.update(
                        status="In Progress",
                        closed_at=None,
                        assignee_id=identifier(assignee or case["assignee_id"]),
                    )
                    validate_references(self.db, "cases", {**case, **changes}, session=sid)
                    event = "reopened"
                elif operation == "resume":
                    if case["status"] != "Awaiting Student":
                        raise AccessDenied("Only Awaiting Student requests can resume.")
                    changes["status"] = "In Progress"
                    event = "resumed"
                elif operation == "note":
                    event = "note_added"
                    template = None
                elif context == "student" and case["status"] == "Awaiting Student":
                    changes["status"] = "In Progress"
                    event = "student_replied"
                if context == "staff":
                    self.db.teams.update_one(
                        {"_id": case["team_id"]},
                        {"$inc": {"authorization_revision": 1}},
                        session=sid,
                    )
                if operation not in {"reopen", "resume"}:
                    doc = {
                        "_id": message_id,
                        "case_id": case_id,
                        "author_id": actor,
                        "body": body,
                        "created_at": now,
                        "author_context": context,
                    }
                    if correction:
                        previous = self.db[collection].find_one(
                            {"_id": correction, "case_id": case_id, "author_id": actor}, session=sid
                        )
                        if not previous:
                            raise AccessDenied("Only your own same-case entry can be corrected.")
                        doc["supersedes_id" if operation == "note" else "correction_of"] = (
                            correction
                        )
                    self.db[collection].insert_one(doc, session=sid)
                self.db.cases.update_one(
                    {"_id": case_id, "version": version},
                    {"$set": changes, "$inc": {"version": 1}},
                    session=sid,
                )
                event_id = str(uuid4())
                event_doc = {
                    "_id": event_id,
                    "case_id": case_id,
                    "actor_id": actor,
                    "event_type": event,
                    "created_at": now,
                }
                if reason:
                    event_doc["reason"] = reason
                self.db.case_events.insert_one(event_doc, session=sid)
                AuditWriter(self.db).append(
                    actor,
                    "communication_changed",
                    "case",
                    case_id,
                    (
                        ["status"]
                        if operation in {"resume", "reopen"}
                        else ["body"]
                        if operation == "note"
                        else ["status", "body"]
                    ),
                    sid,
                )
                if template:
                    Outbox(self.db).enqueue(sid, event_id, case["student_id"], case_id, template)
                return message_id

            if operation == "message" and key_hash:
                return idempotent(self.db, sid, actor, "send_message", key_hash, fingerprint, write)
            return write()

        return transaction(self.db, operation_tx)
