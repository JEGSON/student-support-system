"""Reference integrity checks before trusted service writes; not an access policy."""

from app.repositories.core import InvalidInput, identifier
from app.repositories.schema import CATEGORIES, SCHEMAS

REFERENCES = {
    "account_closures": {"user_id": "users", "reviewed_by": "users"},
    "enrolment_invitations": {"created_by": "users", "accepted_by": "users", "team_id": "teams"},
    "memberships": {"user_id": "users", "team_id": "teams", "granted_by": "users"},
    "cases": {
        "student_id": "users",
        "team_id": "teams",
        "assignee_id": "users",
        "resolution_message_id": "messages",
        "originating_referral_id": "referrals",
    },
    "messages": {"case_id": "cases", "author_id": "users", "correction_of": "messages"},
    "internal_notes": {"case_id": "cases", "author_id": "users", "supersedes_id": "internal_notes"},
    "case_events": {
        "case_id": "cases",
        "actor_id": "users",
        "old_assignee": "users",
        "new_assignee": "users",
    },
    "referrals": {
        "source_case_id": "cases",
        "target_team_id": "teams",
        "requested_by": "users",
        "source_approved_by": "users",
        "decided_by": "users",
        "target_case_id": "cases",
    },
    "audit_events": {"actor_id": "users", "service_id": "service_principals"},
    "notification_outbox": {"recipient_user_id": "users", "case_id": "cases"},
    "sessions": {"user_id": "users"},
    "submission_keys": {"user_id": "users", "result_id": "cases"},
    "triage_claims": {"case_id": "cases", "user_id": "users", "team_id": "teams"},
    "privileged_grants": {
        "user_id": "users",
        "requested_by": "users",
        "approved_by": "users",
        "team_id": "teams",
    },
}


def validate_references(database, collection, document, session=None):
    if not isinstance(collection, str) or collection not in REFERENCES:
        raise InvalidInput("Unsupported reference contract.")
    if not isinstance(document, dict):
        raise InvalidInput("A record object is required.")
    if (
        collection == "audit_events"
        and sum(document.get(field) is not None for field in ("actor_id", "service_id")) != 1
    ):
        raise InvalidInput("An audit event requires exactly one actor or service.")
    contract = SCHEMAS[collection]["$jsonSchema"]
    required = set(contract["required"])
    records = {}
    cache = {}
    # Reference checks need metadata, never message/note bodies or contact details.
    projection = {
        key: 1
        for key in ["_id", "case_id", "global_roles", "account_status", "category_scope", "active"]
    }
    for field, target in REFERENCES[collection].items():
        if (
            collection == "submission_keys"
            and field == "result_id"
            and document.get("operation") == "send_message"
        ):
            target = "messages"
        if field not in document:
            if field in required:
                raise InvalidInput("A required reference is missing.")
            continue
        value = document[field]
        if value is None:
            nullable = any(
                option.get("bsonType") == "null"
                for option in contract["properties"][field].get("anyOf", [])
            )
            if not nullable:
                raise InvalidInput("A reference cannot be null.")
            continue
        key = (target, identifier(value))
        if key not in cache:
            cache[key] = database[target].find_one({"_id": key[1]}, projection, session=session)
        record = cache[key]
        if record is None:
            raise InvalidInput("Referenced record is unavailable.")
        records[field] = record
        if field in {"correction_of", "supersedes_id", "resolution_message_id"} and record[
            "case_id"
        ] != document.get("case_id", document.get("_id")):
            raise InvalidInput("Referenced record belongs to another case.")
    if collection == "cases":
        if (
            "student" not in records["student_id"]["global_roles"]
            and records["student_id"]["account_status"] != "closed"
        ):
            raise InvalidInput("Case ownership requires a student account.")
        team = records["team_id"]
        category = document.get("category")
        if (
            category not in CATEGORIES
            or not team["active"]
            or category not in team["category_scope"]
        ):
            raise InvalidInput("Category routing is unavailable.")
        if document.get("assignee_id"):
            assignee = records["assignee_id"]
            membership = database.memberships.find_one(
                {
                    "user_id": document["assignee_id"],
                    "team_id": document["team_id"],
                    "active": True,
                    "role": {"$in": ["officer", "manager"]},
                },
                {"_id": 1},
                session=session,
            )
            if assignee["account_status"] != "active" or not membership:
                raise InvalidInput("Assignee is not eligible for this team.")
