"""Internal transaction unit; feature services must supply their workflow rules."""

from uuid import uuid4

from app.repositories.core import utc_now
from app.services.access import AccessService
from app.services.audit import AuditWriter
from app.services.outbox import Outbox
from app.services.policy import AccessDenied
from app.services.references import validate_references
from app.services.transactions import VersionConflict

CHANGE_FIELDS = {"status", "team_id", "assignee_id", "priority", "priority_reason"}


class CaseTransactions:
    def __init__(self, database):
        self.db = database

    def change(self, actor, context, action, case_id, version, changes, event_type, template=None):
        """Trusted service API, never bound directly to request dictionaries."""
        if action not in {"update_case", "assign_case", "reopen_case"}:
            raise AccessDenied("A mutation permission is required.")
        if (
            type(version) is not int
            or version < 1
            or not changes
            or not set(changes) <= CHANGE_FIELDS
        ):
            raise ValueError("Invalid mutation.")

        def mutation(sid, case):
            if case["version"] != version:
                raise VersionConflict("The request has changed. Review it and try again.")
            validate_references(self.db, "cases", {**case, **changes}, session=sid)
            now = utc_now()
            self.db.cases.update_one(
                {"_id": case_id, "version": version + 1},
                {"$set": {**changes, "updated_at": now}},
                session=sid,
            )
            event_id = str(uuid4())
            event = {
                "_id": event_id,
                "case_id": case_id,
                "actor_id": actor,
                "event_type": event_type,
                "created_at": now,
            }
            if "status" in changes:
                event.update(old_status=case["status"], new_status=changes["status"])
            self.db.case_events.insert_one(event, session=sid)
            AuditWriter(self.db).append(actor, "case_changed", "case", case_id, list(changes), sid)
            if template:
                Outbox(self.db).enqueue(sid, event_id, case["student_id"], case_id, template)

        return AccessService(self.db).guard(actor, context, action, case_id, mutation)
