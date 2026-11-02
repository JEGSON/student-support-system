"""Scoped staff/triage reads and version-checked work allocation."""

from uuid import uuid4

from app.repositories.core import identifier, plain_text, utc_now
from app.services.access import AccessService
from app.services.audit import AuditWriter
from app.services.policy import AccessDenied, Policy
from app.services.references import validate_references
from app.services.transactions import VersionConflict, transaction

META = {"_id": 1, "reference": 1, "category": 1, "created_at": 1, "status": 1, "team_id": 1}


class StaffCases:
    def __init__(self, database):
        self.db = database

    def scopes(self, actor, sid):
        memberships = list(
            self.db.memberships.find({"user_id": actor, "active": True}, session=sid)
        )
        active = {
            t["_id"]
            for t in self.db.teams.find(
                {"_id": {"$in": [m["team_id"] for m in memberships]}, "active": True},
                {"_id": 1},
                session=sid,
            )
        }
        return [m for m in memberships if m["team_id"] in active]

    def queue(self, actor, context, status=None, after=None):
        def operation(sid):
            Policy(self.db, actor, context, sid)
            if context != "staff":
                raise AccessDenied("Staff context required.")
            scope = self.scopes(actor, sid)
            rules = [
                {
                    "team_id": m["team_id"],
                    **({} if m["role"] in {"manager", "triage"} else {"assignee_id": actor}),
                }
                for m in scope
            ]
            if not rules:
                return [], False
            query = {"archive_state": "active", "$or": rules}
            if status:
                if status not in {"New", "In Progress", "Awaiting Student", "Closed"}:
                    raise ValueError("Invalid status.")
                query["status"] = status
            if after:
                query["_id"] = {"$gt": identifier(after)}
            rows = list(
                self.db.cases.find(query, META, session=sid, max_time_ms=1500)
                .sort("_id", 1)
                .limit(21)
            )
            for row in rows:
                member_roles = {m["role"] for m in scope if m["team_id"] == row["team_id"]}
                row["can_claim"] = row["status"] == "New" and bool(
                    member_roles & {"triage", "manager"}
                )
                team = self.db.teams.find_one({"_id": row["team_id"]}, {"name": 1}, session=sid)
                row["team_name"] = team["name"]
            AccessService(self.db).touch_user(actor, sid)
            AuditWriter(self.db).append(actor, "staff_queue", "user", actor, [], sid)
            return rows[:20], len(rows) > 20

        return transaction(self.db, operation)

    def read(self, actor, context, case_id, triage=False):
        def operation(sid):
            policy = Policy(self.db, actor, context, sid)
            case = self.db.cases.find_one({"_id": identifier(case_id)}, session=sid)
            policy.require("read_initial_request" if triage else "read_case", case)
            if context != "staff":
                raise AccessDenied("Staff context required.")
            AccessService(self.db).touch_user(actor, sid)
            AuditWriter(self.db).append(
                actor, "triage_read" if triage else "case_read", "case", case_id, [], sid
            )
            user = self.db.users.find_one(
                {"_id": case["student_id"]},
                {"display_name": 1, "student_reference": 1},
                session=sid,
            )
            result = {
                k: case[k]
                for k in [
                    "_id",
                    "reference",
                    "category",
                    "description",
                    "status",
                    "version",
                    "team_id",
                    "assignee_id",
                    "created_at",
                    "updated_at",
                ]
            }
            result["student"] = user
            if not triage:
                result["can_assign"] = policy.allows("assign_case", case)
                result["can_reopen"] = policy.allows("reopen_case", case)
                result["officers"] = (
                    list(
                        self.db.memberships.find(
                            {
                                "team_id": case["team_id"],
                                "active": True,
                                "role": {"$in": ["officer", "manager"]},
                            },
                            {"user_id": 1},
                            session=sid,
                        )
                    )
                    if result["can_assign"]
                    else []
                )
            if not triage:
                eligible = []
                for member in result["officers"]:
                    user = self.db.users.find_one(
                        {"_id": member["user_id"], "account_status": "active"},
                        {"display_name": 1},
                        session=sid,
                    )
                    if user:
                        eligible.append(user)
                result["officers"] = eligible
            return result

        return transaction(self.db, operation)

    def mutate(
        self, actor, context, case_id, version, operation, *, assignee=None, team=None, reason=None
    ):
        permission = {
            "assign": "assign_case",
            "start": "update_case",
            "route": "read_initial_request",
        }
        if operation not in permission:
            raise ValueError("Invalid action.")
        reason = plain_text(reason, 1000)

        def change(sid, case):
            if type(version) is not int or case["version"] != version:
                raise VersionConflict("Request changed; review and try again.")
            changes = {}
            event = {"assign": "assigned", "start": "started", "route": "routed"}[operation]
            if operation == "assign":
                if case["status"] == "Closed":
                    raise AccessDenied("Reopen before assigning.")
                target = self.db.users.find_one(
                    {"_id": identifier(assignee), "account_status": "active"}, session=sid
                )
                if not target:
                    raise AccessDenied("Officer unavailable.")
                AccessService(self.db).touch_user(assignee, sid)
                changes["assignee_id"] = assignee
            elif operation == "start":
                if case["status"] != "New" or not case["assignee_id"]:
                    raise AccessDenied("Only an assigned New case can start.")
                changes["status"] = "In Progress"
            else:
                if case["status"] != "New":
                    raise AccessDenied("Only an initial request can be routed.")
                identifier(team)
                self.db.teams.update_one(
                    {"_id": team, "active": True},
                    {"$inc": {"authorization_revision": 1}},
                    session=sid,
                )
                changes.update(team_id=team, assignee_id=None)
                self.db.triage_claims.update_one(
                    {"case_id": case_id, "user_id": actor},
                    {"$set": {"state": "released"}},
                    session=sid,
                )
            candidate = {**case, **changes}
            validate_references(self.db, "cases", candidate, session=sid)
            now = utc_now()
            changes["updated_at"] = now
            self.db.cases.update_one({"_id": case_id}, {"$set": changes}, session=sid)
            self.db.case_events.insert_one(
                {
                    "_id": str(uuid4()),
                    "case_id": case_id,
                    "actor_id": actor,
                    "event_type": event,
                    "reason": reason,
                    "created_at": now,
                },
                session=sid,
            )
            AuditWriter(self.db).append(
                actor,
                "case_changed",
                "case",
                case_id,
                [k for k in changes if k != "updated_at"],
                sid,
            )

        return AccessService(self.db).guard(actor, context, permission[operation], case_id, change)

    def release(self, actor, context, case_id):
        def change(sid, case):
            self.db.triage_claims.update_one(
                {"case_id": case_id, "user_id": actor, "state": "active"},
                {"$set": {"state": "released"}},
                session=sid,
            )
            AuditWriter(self.db).append(actor, "triage_released", "case", case_id, ["claim"], sid)

        return AccessService(self.db).guard(actor, context, "read_initial_request", case_id, change)
