"""Version 1 persistence contracts; these are server-owned schema definitions."""

from copy import deepcopy

ID = {
    "bsonType": "string",
    "pattern": r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
}
DATE = {"bsonType": "date"}
BOOL = {"bsonType": "bool"}
INTEGER = {"bsonType": ["int", "long"], "minimum": 0}
HASH = {"bsonType": "string", "pattern": "^[0-9a-f]{64}$"}
STATUSES = ["New", "In Progress", "Awaiting Student", "Closed"]
CATEGORIES = ["academic", "finance", "wellbeing", "disability", "accommodation"]
GLOBAL_ROLES = ["student", "administrator", "access_approver", "audit_reviewer"]


def text(maximum, minimum=1):
    return {
        "bsonType": "string",
        "minLength": minimum,
        "maxLength": maximum,
        "pattern": r"\S" if minimum else r".*",
    }


def enum(values):
    return {"enum": values}


def array(items):
    return {"bsonType": "array", "items": items, "uniqueItems": True, "maxItems": 20}


def nullable(spec):
    return {"anyOf": [spec, {"bsonType": "null"}]}


def schema(required, **properties):
    return {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["_id", *required],
            "additionalProperties": False,
            "properties": {
                "_id": deepcopy(ID),
                "fixture_version": enum(["synthetic-v1"]),
                **properties,
            },
        }
    }


SCHEMAS = {
    "users": schema(
        [
            "identity_issuer",
            "identity_subject",
            "display_name",
            "account_status",
            "global_roles",
            "authorization_revision",
            "created_at",
        ],
        identity_issuer=text(500),
        identity_subject=text(255),
        student_reference=text(80),
        display_name=text(160),
        verified_contact=text(254),
        course_label=text(160),
        account_status=enum(["active", "disabled"]),
        global_roles=array(enum(GLOBAL_ROLES)),
        authorization_revision=INTEGER,
        guard_version=INTEGER,
        created_at=DATE,
    ),
    "teams": schema(
        ["name", "category_scope", "active", "authorization_revision"],
        name=text(100),
        category_scope=array(enum(CATEGORIES)),
        active=BOOL,
        authorization_revision=INTEGER,
    ),
    "memberships": schema(
        ["user_id", "team_id", "role", "active", "granted_by", "granted_at"],
        user_id=ID,
        team_id=ID,
        role=enum(["triage", "officer", "manager"]),
        active=BOOL,
        granted_by=ID,
        granted_at=DATE,
        revoked_at=nullable(DATE),
    ),
    "cases": schema(
        [
            "reference",
            "student_id",
            "category",
            "description",
            "team_id",
            "assignee_id",
            "status",
            "priority",
            "version",
            "created_at",
            "updated_at",
            "archive_state",
            "legal_hold",
        ],
        reference=text(40),
        student_id=ID,
        category=enum(CATEGORIES),
        description=text(10000),
        team_id=ID,
        assignee_id=nullable(ID),
        status=enum(STATUSES),
        priority=enum(["standard", "urgent"]),
        priority_reason=text(1000),
        version={"bsonType": ["int", "long"], "minimum": 1},
        created_at=DATE,
        updated_at=DATE,
        closed_at=nullable(DATE),
        resolution_message_id=nullable(ID),
        archive_state=enum(["active", "archived"]),
        retention_review_at=nullable(DATE),
        legal_hold=BOOL,
        originating_referral_id=ID,
    ),
    "messages": schema(
        ["case_id", "author_id", "body", "created_at"],
        case_id=ID,
        author_id=ID,
        author_context=enum(["student", "staff"]),
        body=text(10000),
        created_at=DATE,
        correction_of=nullable(ID),
    ),
    "internal_notes": schema(
        ["case_id", "author_id", "body", "created_at"],
        case_id=ID,
        author_id=ID,
        author_context=enum(["student", "staff"]),
        body=text(10000),
        created_at=DATE,
        supersedes_id=nullable(ID),
    ),
    "case_events": schema(
        ["case_id", "actor_id", "event_type", "created_at"],
        case_id=ID,
        actor_id=ID,
        event_type=enum(
            [
                "submitted",
                "assigned",
                "routed",
                "started",
                "information_requested",
                "student_replied",
                "message_added",
                "note_added",
                "closed",
                "reopened",
                "resumed",
                "archived",
                "referral_created",
            ]
        ),
        old_status=enum(STATUSES),
        new_status=enum(STATUSES),
        old_assignee=nullable(ID),
        new_assignee=nullable(ID),
        reason=text(1000),
        created_at=DATE,
    ),
    "referrals": schema(
        [
            "source_case_id",
            "target_team_id",
            "requested_by",
            "purpose",
            "shared_summary",
            "status",
            "created_at",
        ],
        source_case_id=ID,
        target_team_id=ID,
        requested_by=ID,
        purpose=text(1000),
        shared_summary=text(3000),
        status=enum(["proposed", "source_approved", "accepted", "rejected", "withdrawn"]),
        created_at=DATE,
        source_approved_by=ID,
        decided_by=ID,
        decided_at=DATE,
        target_case_id=nullable(ID),
    ),
    "audit_events": schema(
        [
            "action",
            "target_type",
            "target_id",
            "outcome",
            "occurred_at",
            "request_id",
            "changed_field_names",
        ],
        actor_id=ID,
        service_id=ID,
        action=text(80),
        target_type=text(40),
        target_id=ID,
        outcome=enum(["allowed", "denied", "failed"]),
        occurred_at=DATE,
        request_id=text(64),
        changed_field_names=array(text(80)),
    ),
    "notification_outbox": schema(
        [
            "event_key",
            "recipient_user_id",
            "case_id",
            "template_key",
            "channel",
            "state",
            "attempts",
            "next_attempt_at",
            "created_at",
        ],
        event_key=text(160),
        recipient_user_id=ID,
        case_id=ID,
        template_key=enum(
            ["case_received", "case_updated", "information_requested", "case_closed"]
        ),
        channel=enum(["email"]),
        state=enum(["pending", "leased", "sent", "dead"]),
        attempts=INTEGER,
        next_attempt_at=DATE,
        lease_hash=HASH,
        lease_until=nullable(DATE),
        created_at=DATE,
        expires_at=DATE,
    ),
    "sessions": schema(
        [
            "token_hash",
            "user_id",
            "created_at",
            "last_seen_at",
            "idle_expires_at",
            "absolute_expires_at",
            "authentication_time",
        ],
        token_hash=HASH,
        data={"bsonType": "object", "maxProperties": 8},
        version=INTEGER,
        user_id=ID,
        created_at=DATE,
        last_seen_at=DATE,
        idle_expires_at=DATE,
        absolute_expires_at=DATE,
        revoked_at=nullable(DATE),
        authentication_time=DATE,
        context=enum(["student", "staff", "admin", "audit"]),
    ),
    "auth_attempts": schema(
        [
            "token_hash",
            "data",
            "version",
            "created_at",
            "last_seen_at",
            "idle_expires_at",
            "absolute_expires_at",
        ],
        token_hash=HASH,
        data={"bsonType": "object", "maxProperties": 8},
        version=INTEGER,
        created_at=DATE,
        last_seen_at=DATE,
        idle_expires_at=DATE,
        absolute_expires_at=DATE,
        revoked_at=nullable(DATE),
    ),
    "submission_keys": schema(
        ["user_id", "operation", "key_hash", "expires_at"],
        user_id=ID,
        operation=enum(["create_case", "send_message"]),
        key_hash=HASH,
        result_id=ID,
        payload_hash=HASH,
        expires_at=DATE,
    ),
    "triage_claims": schema(
        [
            "case_id",
            "user_id",
            "team_id",
            "created_at",
            "expires_at",
            "state",
            "authorization_revision",
            "version",
        ],
        case_id=ID,
        user_id=ID,
        team_id=ID,
        created_at=DATE,
        expires_at=DATE,
        state=enum(["active", "released"]),
        authorization_revision=INTEGER,
        version={"bsonType": ["int", "long"], "minimum": 1},
    ),
    "privileged_grants": schema(
        ["user_id", "role", "requested_by", "reason", "state", "created_at"],
        user_id=ID,
        team_id=ID,
        role=enum(["manager", "administrator", "access_approver", "audit_reviewer"]),
        requested_by=ID,
        reason=text(1000),
        state=enum(["pending", "approved", "rejected", "revoked"]),
        approved_by=nullable(ID),
        decided_at=nullable(DATE),
        decision_reason=text(1000),
        created_at=DATE,
    ),
    "service_principals": schema(
        ["name", "kind", "active", "authorization_revision"],
        name=text(100),
        kind=enum(["notification_worker"]),
        active=BOOL,
        authorization_revision=INTEGER,
    ),
}
SCHEMAS["audit_events"]["$jsonSchema"]["oneOf"] = [
    {"required": ["actor_id"]},
    {"required": ["service_id"]},
]

# Each entry: keys, options. No TTL for cases or triage claims; expiry must be checked in policy.
INDEXES = {
    "users": [
        ([("identity_issuer", 1), ("identity_subject", 1)], {"unique": True}),
        (
            [("student_reference", 1)],
            {"unique": True, "partialFilterExpression": {"student_reference": {"$type": "string"}}},
        ),
    ],
    "teams": [([("name", 1)], {"unique": True})],
    "memberships": [
        ([("user_id", 1), ("team_id", 1), ("role", 1)], {"unique": True}),
        ([("user_id", 1), ("active", 1)], {}),
    ],
    "cases": [
        ([("reference", 1)], {"unique": True}),
        ([("student_id", 1), ("updated_at", -1), ("_id", -1)], {}),
        ([("team_id", 1), ("status", 1), ("updated_at", -1), ("_id", -1)], {}),
        ([("assignee_id", 1), ("status", 1), ("updated_at", -1), ("_id", -1)], {}),
        (
            [("originating_referral_id", 1)],
            {
                "unique": True,
                "partialFilterExpression": {"originating_referral_id": {"$type": "string"}},
            },
        ),
    ],
    "messages": [([("case_id", 1), ("created_at", 1), ("_id", 1)], {})],
    "internal_notes": [([("case_id", 1), ("created_at", 1), ("_id", 1)], {})],
    "case_events": [([("case_id", 1), ("created_at", 1), ("_id", 1)], {})],
    "referrals": [([("target_team_id", 1), ("status", 1), ("created_at", 1)], {})],
    "audit_events": [
        ([("target_id", 1), ("occurred_at", 1)], {}),
        ([("actor_id", 1), ("occurred_at", 1)], {}),
    ],
    "notification_outbox": [
        ([("event_key", 1), ("recipient_user_id", 1), ("channel", 1)], {"unique": True}),
        ([("state", 1), ("next_attempt_at", 1)], {}),
    ],
    "sessions": [
        ([("token_hash", 1)], {"unique": True}),
        ([("absolute_expires_at", 1)], {"expireAfterSeconds": 0}),
    ],
    "auth_attempts": [
        ([("token_hash", 1)], {"unique": True}),
        ([("absolute_expires_at", 1)], {"expireAfterSeconds": 0}),
    ],
    "submission_keys": [
        ([("user_id", 1), ("operation", 1), ("key_hash", 1)], {"unique": True}),
        ([("expires_at", 1)], {"expireAfterSeconds": 0}),
    ],
    "triage_claims": [([("case_id", 1)], {"unique": True}), ([("expires_at", 1)], {})],
    "privileged_grants": [([("user_id", 1), ("state", 1), ("created_at", 1)], {})],
    "service_principals": [([("name", 1)], {"unique": True})],
}

# Session revocation and bounded access-administration lookup paths.
INDEXES["sessions"].append(([("user_id", 1), ("revoked_at", 1)], {}))
INDEXES["users"].append(([("display_name", 1), ("_id", 1)], {}))
INDEXES["privileged_grants"].extend(
    [
        ([("state", 1), ("created_at", 1)], {}),
        ([("user_id", 1), ("role", 1), ("team_id", 1), ("state", 1)], {}),
    ]
)

# Additive index for the actual active-case keyset query. Preserve baseline indexes
# until workload evidence justifies removing any redundant one.
INDEXES["cases"].append(
    ([("student_id", 1), ("archive_state", 1), ("updated_at", -1), ("_id", -1)], {})
)


def install_schema(database):
    """Explicit privileged setup, never called from public application startup."""
    if database.name not in {"student_support_dev", "student_support_test"}:
        raise ValueError("Schema setup is limited to isolated local databases.")
    existing = set(database.list_collection_names())
    for name, validator in SCHEMAS.items():
        if name in existing:
            database.command(
                "collMod",
                name,
                validator=deepcopy(validator),
                validationLevel="strict",
                validationAction="error",
            )
        else:
            database.create_collection(
                name,
                validator=deepcopy(validator),
                validationLevel="strict",
                validationAction="error",
            )
        for number, (keys, options) in enumerate(INDEXES[name], 1):
            database[name].create_index(keys, name=f"{name}_v1_{number}", **options)
    return len(SCHEMAS)
