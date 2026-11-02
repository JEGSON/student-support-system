"""Central deny-by-default policy. Caller-supplied identity or roles are never trusted."""

from datetime import timedelta

from app.repositories.core import identifier, utc_now


class AccessDenied(PermissionError):
    pass


class Policy:
    def __init__(self, database, user_id, context, db_session=None):
        self.db = database
        self.sid = db_session
        self.context = context
        self.user = database.users.find_one(
            {"_id": identifier(user_id), "account_status": "active"}, session=db_session
        )
        if not self.user:
            raise AccessDenied("Access denied.")

    def global_role(self, role):
        return self.context == "admin" and role in self.user["global_roles"]

    def membership(self, team_id, roles):
        return self.context == "staff" and bool(
            self.db.teams.find_one({"_id": team_id, "active": True}, session=self.sid)
            and self.db.memberships.find_one(
                {
                    "user_id": self.user["_id"],
                    "team_id": team_id,
                    "role": {"$in": list(roles)},
                    "active": True,
                },
                session=self.sid,
            )
        )

    def allows(self, action, case=None, purpose=None):
        if action in {"manage_accounts", "request_grant"}:
            return self.global_role("administrator")
        if action == "approve_grant":
            return self.global_role("access_approver")
        if not case or case.get("archive_state") != "active":
            return False
        student = (
            self.context == "student"
            and "student" in self.user["global_roles"]
            and case["student_id"] == self.user["_id"]
        )
        manager = self.membership(case["team_id"], {"manager"})
        assigned = case["assignee_id"] == self.user["_id"] and self.membership(
            case["team_id"], {"officer"}
        )
        if action in {"read_case", "read_messages"}:
            return student or manager or assigned
        if action == "send_message":
            return case["status"] != "Closed" and (student or manager or assigned)
        if action in {"read_notes", "write_note", "update_case"}:
            return manager or assigned
        if action in {"assign_case", "reopen_case", "approve_referral"}:
            return manager
        if action == "claim_triage" and case["status"] != "New":
            return False
        if action in {"triage_metadata", "claim_triage"}:
            return self.membership(case["team_id"], {"triage", "manager"})
        if action == "read_initial_request":
            if not self.membership(case["team_id"], {"triage", "manager"}):
                return False
            now = utc_now()
            claim = self.db.triage_claims.find_one(
                {
                    "case_id": case["_id"],
                    "user_id": self.user["_id"],
                    "team_id": case["team_id"],
                    "state": "active",
                    "authorization_revision": self.user["authorization_revision"],
                    "created_at": {"$lte": now, "$gte": now - timedelta(minutes=30)},
                    "expires_at": {"$gt": now, "$lte": now + timedelta(minutes=30)},
                },
                session=self.sid,
            )
            return bool(
                claim
                and case["status"] == "New"
                and claim["expires_at"] - claim["created_at"] <= timedelta(minutes=30)
            )
        if action == "read_audit":
            return (
                self.context == "audit"
                and "audit_reviewer" in self.user["global_roles"]
                and bool(
                    self.db.teams.find_one(
                        {"_id": case["team_id"], "active": True}, session=self.sid
                    )
                )
                and isinstance(purpose, str)
                and 1 <= len(purpose.strip()) <= 1000
                and bool(
                    self.db.privileged_grants.find_one(
                        {
                            "user_id": self.user["_id"],
                            "team_id": case["team_id"],
                            "role": "audit_reviewer",
                            "state": "approved",
                        },
                        session=self.sid,
                    )
                )
            )
        return False

    def require(self, action, case=None, **kwargs):
        if not self.allows(action, case, **kwargs):
            raise AccessDenied("Access denied.")


def worker_allows(principal, action):
    return bool(
        principal
        and principal.get("active")
        and principal.get("kind") == "notification_worker"
        and action in {"lease_notification", "read_delivery_contact", "record_delivery"}
    )


TRIAGE_FIELDS = {"reference", "category", "created_at", "status", "team_id"}


def triage_view(case):
    return {key: case[key] for key in TRIAGE_FIELDS}
