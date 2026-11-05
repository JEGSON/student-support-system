"""Deliberate summary sharing; acceptance never copies source narrative or notes."""

import secrets
from uuid import uuid4

from app.repositories.core import identifier, plain_text, utc_now
from app.services.access import AccessService
from app.services.audit import AuditWriter
from app.services.outbox import Outbox
from app.services.policy import AccessDenied, Policy
from app.services.transactions import transaction


class Referrals:
    def __init__(self, database):
        self.db = database

    def propose(self, actor, context, case_id, target, category, purpose, summary):
        purpose = plain_text(purpose, 1000)
        summary = plain_text(summary, 3000)
        identifier(target)
        referral_id = str(uuid4())

        def write(sid, case):
            if case["assignee_id"] != actor or case["status"] == "Closed":
                raise AccessDenied("Only the assigned officer can propose an active-case referral.")
            team = self.db.teams.find_one(
                {"_id": target, "active": True, "category_scope": category}, session=sid
            )
            if not team or target == case["team_id"]:
                raise AccessDenied("Choose a different eligible team.")
            self.db.referrals.insert_one(
                {
                    "_id": referral_id,
                    "source_case_id": case_id,
                    "source_team_id": case["team_id"],
                    "target_team_id": target,
                    "target_category": category,
                    "requested_by": actor,
                    "purpose": purpose,
                    "shared_summary": summary,
                    "status": "proposed",
                    "created_at": utc_now(),
                },
                session=sid,
            )
            AuditWriter(self.db).append(actor, "referral_changed", "case", case_id, [], sid)
            return referral_id

        return AccessService(self.db).guard(actor, context, "update_case", case_id, write)

    def list(self, actor, context):
        def read(sid):
            policy = Policy(self.db, actor, context, sid)
            if context != "staff":
                raise AccessDenied("Staff context required.")
            manager_teams = [
                m["team_id"]
                for m in self.db.memberships.find(
                    {"user_id": actor, "active": True, "role": "manager"}, session=sid
                )
                if policy.membership(m["team_id"], {"manager"})
            ]
            source_ids = [
                c["_id"]
                for c in self.db.cases.find(
                    {"team_id": {"$in": manager_teams}, "archive_state": "active"},
                    {"_id": 1},
                    session=sid,
                ).limit(1000)
            ]
            rows = list(
                self.db.referrals.find(
                    {
                        "$or": [
                            {"requested_by": actor},
                            {"source_case_id": {"$in": source_ids}},
                            {
                                "target_team_id": {"$in": manager_teams},
                                "status": {"$in": ["source_approved", "accepted", "rejected"]},
                            },
                        ]
                    },
                    session=sid,
                    max_time_ms=1500,
                )
                .sort("created_at", -1)
                .limit(100)
            )
            result = []
            for row in rows:
                case = self.db.cases.find_one(
                    {"_id": row["source_case_id"]},
                    {
                        "student_id": 1,
                        "team_id": 1,
                        "archive_state": 1,
                        "assignee_id": 1,
                        "status": 1,
                    },
                    session=sid,
                )
                if not case:
                    continue
                can_source = policy.allows("read_case", case)
                can_target = policy.membership(row["target_team_id"], {"manager"}) and row[
                    "status"
                ] in {"source_approved", "accepted", "rejected"}
                if not can_source and not can_target:
                    continue
                student = self.db.users.find_one(
                    {"_id": case["student_id"]}, {"display_name": 1}, session=sid
                )
                result.append(
                    {
                        "_id": row["_id"],
                        "purpose": row["purpose"],
                        "summary": row["shared_summary"],
                        "status": row["status"],
                        "student": student["display_name"],
                        "source": case["team_id"] in manager_teams,
                        "target": can_target,
                        "target_case_id": row.get("target_case_id"),
                    }
                )
            AccessService(self.db).touch_user(actor, sid)
            AuditWriter(self.db).append(actor, "referrals_read", "user", actor, [], sid)
            return result

        return transaction(self.db, read)

    def decide(self, actor, context, referral_id, decision, reason):
        reason = plain_text(reason, 1000)
        if decision not in {"approve", "accept", "reject", "withdraw"}:
            raise ValueError("Invalid referral decision.")
        target_id = str(uuid4())

        def operation(sid):
            policy = Policy(self.db, actor, context, sid)
            referral = self.db.referrals.find_one({"_id": identifier(referral_id)}, session=sid)
            if not referral:
                raise AccessDenied("Referral unavailable.")
            source = self.db.cases.find_one(
                {"_id": referral["source_case_id"]},
                {
                    "student_id": 1,
                    "team_id": 1,
                    "archive_state": 1,
                    "assignee_id": 1,
                    "status": 1,
                },
                session=sid,
            )
            if not source or source["archive_state"] != "active":
                raise AccessDenied("Source unavailable.")
            target_manager = policy.membership(referral["target_team_id"], {"manager"})
            source_manager = policy.membership(source["team_id"], {"manager"})
            state = referral["status"]
            changes = {"decided_by": actor, "decided_at": utc_now(), "decision_reason": reason}
            if decision == "approve":
                if not source_manager or state != "proposed":
                    raise AccessDenied("Source manager approval required.")
                changes.update(status="source_approved", source_approved_by=actor)
            elif decision == "withdraw":
                if not source_manager or state not in {"proposed", "source_approved"}:
                    raise AccessDenied("Source manager withdrawal required.")
                changes["status"] = "withdrawn"
            else:
                if not target_manager:
                    raise AccessDenied("Target manager required.")
                if decision == "accept" and state == "accepted":
                    return referral["target_case_id"]
                if state != "source_approved":
                    raise AccessDenied("Source approval is required.")
                if decision == "reject":
                    changes["status"] = "rejected"
                else:
                    if source["team_id"] != referral.get("source_team_id"):
                        raise AccessDenied("Source scope changed; request renewed approval.")
                    approver = Policy(self.db, referral["source_approved_by"], "staff", sid)
                    if not approver.membership(source["team_id"], {"manager"}):
                        raise AccessDenied("Source approval is no longer current.")
                    AccessService(self.db).touch_user(referral["source_approved_by"], sid)
                    team = self.db.teams.find_one(
                        {
                            "_id": referral["target_team_id"],
                            "active": True,
                            "category_scope": referral.get("target_category"),
                        },
                        session=sid,
                    )
                    if not team:
                        raise AccessDenied("Target unavailable.")
                    now = utc_now()
                    case = {
                        "_id": target_id,
                        "reference": "SS-" + secrets.token_hex(8).upper(),
                        "student_id": source["student_id"],
                        "category": referral["target_category"],
                        "description": referral["shared_summary"],
                        "team_id": referral["target_team_id"],
                        "assignee_id": None,
                        "status": "New",
                        "priority": "standard",
                        "version": 1,
                        "created_at": now,
                        "updated_at": now,
                        "archive_state": "active",
                        "legal_hold": False,
                        "originating_referral_id": referral_id,
                    }
                    self.db.cases.insert_one(case, session=sid)
                    event_id = str(uuid4())
                    self.db.case_events.insert_one(
                        {
                            "_id": event_id,
                            "case_id": target_id,
                            "actor_id": actor,
                            "event_type": "referral_created",
                            "created_at": now,
                        },
                        session=sid,
                    )
                    AuditWriter(self.db).append(
                        actor, "referral_changed", "case", target_id, [], sid
                    )
                    Outbox(self.db).enqueue(
                        sid, event_id, source["student_id"], target_id, "case_received"
                    )
                    changes.update(status="accepted", target_case_id=target_id)
            AccessService(self.db).touch_user(actor, sid)
            # Serialize source routing/archiving against this decision. Source
            # case business fields remain unchanged; their services share this guard.
            self.db.teams.update_one(
                {"_id": source["team_id"]},
                {"$inc": {"authorization_revision": 1}},
                session=sid,
            )
            self.db.teams.update_one(
                {"_id": referral["target_team_id"]},
                {"$inc": {"authorization_revision": 1}},
                session=sid,
            )
            self.db.referrals.update_one(
                {"_id": referral_id, "status": state}, {"$set": changes}, session=sid
            )
            AuditWriter(self.db).append(actor, "referral_changed", "case", source["_id"], [], sid)
            return changes.get("target_case_id")

        return transaction(self.db, operation)
