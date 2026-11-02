"""Actual validator/index/reference tests on the isolated MongoDB replica set."""

import os
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import dotenv_values
from pymongo.errors import DuplicateKeyError, WriteError

from app.repositories.core import InvalidInput, Repositories
from app.repositories.fixtures import VERSION, fixture_documents, fixture_id, seed_fixtures
from app.repositories.schema import INDEXES, SCHEMAS, install_schema
from app.services.references import validate_references
from scripts.database_setup import local_client

pytestmark = [
    pytest.mark.runtime,
    pytest.mark.skipif(
        os.getenv("RUN_RUNTIME") != "1", reason="Requires isolated local replica set"
    ),
]


@pytest.fixture(scope="module")
def database():
    values = dotenv_values(Path(__file__).resolve().parents[2] / ".env")
    schema_client = local_client(values, "schema")
    client = local_client(values, "testing")
    db = client.student_support_test
    assert install_schema(schema_client.student_support_test) == len(SCHEMAS)
    assert install_schema(schema_client.student_support_test) == len(SCHEMAS)
    seed_fixtures(db, values["OIDC_ISSUER"])
    yield db
    client.close()
    schema_client.close()


def sample_documents():
    stamp = datetime.now(timezone.utc)
    uid, cid, tid = fixture_id("student_a"), fixture_id("case_a"), fixture_id("team_finance")
    docs = {
        name: deepcopy(records[0])
        for name, records in fixture_documents(
            "http://127.0.0.1:8180/realms/student-support"
        ).items()
    }
    docs.update(
        {
            "rate_limits": dict(count=1, expires_at=stamp),
            "disposal_records": dict(
                case_id=cid,
                requested_by=uid,
                policy="synthetic-demo-1day",
                reason="Synthetic disposal review",
                state="pending",
                created_at=stamp,
            ),
            "case_events": dict(
                case_id=cid, actor_id=uid, event_type="submitted", created_at=stamp
            ),
            "referrals": dict(
                source_case_id=cid,
                target_team_id=tid,
                requested_by=uid,
                purpose="Synthetic test",
                shared_summary="Synthetic summary",
                status="proposed",
                created_at=stamp,
            ),
            "audit_events": dict(
                actor_id=uid,
                action="synthetic_test",
                target_type="case",
                target_id=cid,
                outcome="allowed",
                occurred_at=stamp,
                request_id="synthetic",
                changed_field_names=[],
            ),
            "notification_outbox": dict(
                event_key="synthetic-test",
                recipient_user_id=uid,
                case_id=cid,
                template_key="case_received",
                channel="email",
                state="pending",
                attempts=0,
                next_attempt_at=stamp,
                created_at=stamp,
            ),
            "sessions": dict(
                token_hash="0" * 64,
                user_id=uid,
                created_at=stamp,
                last_seen_at=stamp,
                idle_expires_at=stamp + timedelta(minutes=30),
                absolute_expires_at=stamp + timedelta(hours=8),
                authentication_time=stamp,
            ),
            "auth_attempts": dict(
                token_hash="2" * 64,
                data={},
                version=0,
                created_at=stamp,
                last_seen_at=stamp,
                idle_expires_at=stamp + timedelta(minutes=10),
                absolute_expires_at=stamp + timedelta(minutes=10),
            ),
            "submission_keys": dict(
                user_id=uid,
                operation="create_case",
                key_hash="1" * 64,
                expires_at=stamp + timedelta(hours=1),
            ),
            "triage_claims": dict(
                case_id=cid,
                user_id=fixture_id("triage"),
                team_id=tid,
                created_at=stamp,
                expires_at=stamp + timedelta(minutes=30),
                state="active",
                authorization_revision=0,
                version=1,
            ),
            "privileged_grants": dict(
                user_id=uid,
                role="manager",
                requested_by=fixture_id("administrator"),
                reason="Synthetic test",
                state="pending",
                created_at=stamp,
            ),
        }
    )
    for doc in docs.values():
        doc["_id"] = str(uuid4())
    return docs


@pytest.mark.parametrize("name", list(SCHEMAS))
def test_strict_validator_rejects_unknown_fields_and_wrong_id(database, name):
    record = sample_documents()[name]
    for invalid, expected in [
        ({**record, "unexpected_owner": {"$ne": None}}, 121),
        ({**record, "_id": {"$ne": None}}, 52),
        ({**record, "_id": 123}, 121),
    ]:
        with pytest.raises(WriteError) as error:
            database[name].insert_one(invalid)
        assert error.value.code == expected


@pytest.mark.parametrize("name", list(SCHEMAS))
def test_valid_contract_roundtrip_in_aborted_transaction(database, name):
    record = sample_documents()[name]
    # Avoid fixture unique indexes; the goal is valid BSON/schema shape.
    if name == "users":
        record["identity_subject"] = "synthetic-test:" + record["_id"]
        record["student_reference"] = record["_id"]
    if name == "teams":
        record["name"] = "Synthetic " + record["_id"]
    if name == "memberships":
        record["user_id"] = str(uuid4())
    if name == "cases":
        record["reference"] = "SS-TEST-" + record["_id"][:8]
    if name == "service_principals":
        record["name"] = "Synthetic " + record["_id"]
    with database.client.start_session() as session:
        session.start_transaction()
        database[name].insert_one(record, session=session)
        assert database[name].find_one({"_id": record["_id"]}, session=session) is not None
        session.abort_transaction()
    assert database[name].find_one({"_id": record["_id"]}) is None


@pytest.mark.parametrize(
    "name,field",
    [
        ("users", "identity_subject"),
        ("users", "student_reference"),
        ("cases", "reference"),
        ("memberships", "user_id"),
        ("sessions", "token_hash"),
        ("submission_keys", "key_hash"),
        ("notification_outbox", "event_key"),
    ],
)
def test_unique_contracts(database, name, field):
    first = sample_documents()[name]
    if name == "users":
        first["identity_subject"] = "synthetic-unique:" + first["_id"]
        first["student_reference"] = first["_id"]
    if name == "cases":
        first["reference"] = "SS-UNIQUE-" + first["_id"][:8]
    if name == "memberships":
        first["user_id"] = str(uuid4())
    second = deepcopy(first)
    second["_id"] = str(uuid4())
    if name == "users" and field == "identity_subject":
        second["student_reference"] = second["_id"]
    if name == "users" and field == "student_reference":
        second["identity_subject"] = second["_id"]
    with database.client.start_session() as session:
        with pytest.raises(DuplicateKeyError):
            with session.start_transaction():
                database[name].insert_one(first, session=session)
                database[name].insert_one(second, session=session)
    assert database[name].find_one({"_id": first["_id"]}) is None


def test_fixture_idempotency_and_indexes(database):
    before = {
        name: database[name].count_documents({"fixture_version": VERSION}) for name in SCHEMAS
    }
    seed_fixtures(database, "http://127.0.0.1:8180/realms/student-support")
    assert before == {
        name: database[name].count_documents({"fixture_version": VERSION}) for name in SCHEMAS
    }
    assert before["users"] == 12 and before["teams"] == 5 and before["cases"] == 4
    for name, indexes in INDEXES.items():
        installed = database[name].index_information()
        for i, (_, options) in enumerate(indexes, 1):
            assert f"{name}_v1_{i}" in installed
            if options.get("unique"):
                assert installed[f"{name}_v1_{i}"]["unique"]
    assert all(
        "expireAfterSeconds" not in index for index in database.cases.index_information().values()
    )


def test_service_references_and_assignment_consistency(database):
    case = database.cases.find_one({"_id": fixture_id("case_a")})
    validate_references(database, "cases", case)
    for changed in [
        {"student_id": str(uuid4())},
        {"student_id": {"$ne": None}},
        {"student_id": fixture_id("administrator")},
        {"assignee_id": fixture_id("officer_other")},
        {"category": "disability"},
    ]:
        with pytest.raises(InvalidInput):
            validate_references(database, "cases", {**case, **changed})
    note = dict(
        case_id=fixture_id("case_b"),
        author_id=fixture_id("officer_assigned"),
        supersedes_id=fixture_id("note_a"),
    )
    with pytest.raises(InvalidInput):
        validate_references(database, "internal_notes", note)


def test_scoped_stable_pagination_and_malformed_ids(database):
    repo = Repositories(database)
    first = repo.student_cases(fixture_id("student_a"), limit=1)
    assert len(first) == 1
    next_page = repo.student_cases(
        fixture_id("student_a"), limit=1, after=(first[0]["updated_at"], first[0]["_id"])
    )
    assert len(next_page) == 1 and next_page[0]["_id"] < first[0]["_id"]
    assert not repo.student_cases(
        fixture_id("student_a"), after=(next_page[0]["updated_at"], next_page[0]["_id"])
    )
    for value in [None, {"$ne": None}, "bad-id", "A" * 36]:
        with pytest.raises(InvalidInput):
            repo.get_case(value)
    with pytest.raises(InvalidInput):
        repo.student_cases(fixture_id("student_a"), limit=True)
    with pytest.raises(InvalidInput):
        repo.student_cases(fixture_id("student_a"), after={"$where": "anything"})


@pytest.mark.parametrize(
    "name,changes",
    [
        ("cases", {"description": ""}),
        ("cases", {"description": " " * 5}),
        ("cases", {"description": "x" * 10001}),
        ("cases", {"status": "Resolved"}),
        ("cases", {"version": True}),
        ("cases", {"created_at": "2026-11-02"}),
        ("messages", {"body": {"$where": "injected"}}),
        ("internal_notes", {"body": "x" * 10001}),
        ("memberships", {"role": "administrator"}),
        ("notification_outbox", {"attempts": -1}),
        ("sessions", {"token_hash": "not-a-hash"}),
        ("users", {"global_roles": ["superuser"]}),
    ],
)
def test_invalid_enumerations_lengths_types_and_limits(database, name, changes):
    record = {**sample_documents()[name], **changes}
    with pytest.raises(WriteError) as error:
        database[name].insert_one(record)
    assert error.value.code == 121


def test_originating_referral_uniqueness(database):
    first = sample_documents()["cases"]
    first.update(reference="SS-ORIGIN-A", originating_referral_id=str(uuid4()))
    second = {**first, "_id": str(uuid4()), "reference": "SS-ORIGIN-B"}
    with database.client.start_session() as session:
        with pytest.raises(DuplicateKeyError):
            with session.start_transaction():
                database.cases.insert_one(first, session=session)
                database.cases.insert_one(second, session=session)


def test_safe_fixture_reset_preserves_unlabelled_data_and_rejects_dependencies(database):
    from app.repositories.fixtures import reset_fixtures

    mappings = list(database.users.find({"fixture_version": VERSION}, {"identity_subject": 1}))
    standalone = sample_documents()["users"]
    standalone["identity_subject"] = "synthetic-reset:" + standalone["_id"]
    standalone.pop("student_reference", None)
    dependency = sample_documents()["messages"]
    database.users.insert_one(standalone)
    try:
        database.messages.insert_one(dependency)
        with pytest.raises(InvalidInput, match="orphan"):
            reset_fixtures(database)
        assert database.cases.find_one({"_id": fixture_id("case_a")}) is not None
        database.messages.delete_one({"_id": dependency["_id"]})
        reset_fixtures(database)
        assert database.cases.count_documents({"fixture_version": VERSION}) == 0
        assert database.users.find_one({"_id": standalone["_id"]}) is not None
    finally:
        database.messages.delete_one({"_id": dependency["_id"]})
        database.users.delete_one({"_id": standalone["_id"]})
        seed_fixtures(database, "http://127.0.0.1:8180/realms/student-support")
        for user in mappings:
            database.users.update_one(
                {"_id": user["_id"]}, {"$set": {"identity_subject": user["identity_subject"]}}
            )


def test_schema_setup_privileges_are_separate(database):
    from pymongo.errors import OperationFailure

    with pytest.raises(OperationFailure) as error:
        database.command(
            "collMod",
            "cases",
            validator=SCHEMAS["cases"],
            validationLevel="strict",
            validationAction="error",
        )
    assert error.value.code == 13
    values = dotenv_values(Path(__file__).resolve().parents[2] / ".env")
    with local_client(values, "schema") as client:
        with pytest.raises(OperationFailure) as error:
            client.student_support_test.cases.find_one({})
        assert error.value.code == 13


@pytest.mark.parametrize(
    "collection,document",
    [
        ("messages", {"case_id": None, "author_id": fixture_id("student_a")}),
        ("messages", {"author_id": fixture_id("student_a")}),
        ("internal_notes", {"case_id": fixture_id("case_a")}),
        (
            "memberships",
            {
                "user_id": fixture_id("student_a"),
                "team_id": None,
                "granted_by": fixture_id("administrator"),
            },
        ),
        ("sessions", {"user_id": None}),
        ("audit_events", {}),
        ("audit_events", {"actor_id": fixture_id("student_a"), "service_id": fixture_id("worker")}),
    ],
)
def test_required_reference_integrity_rejected_before_write(database, collection, document):
    with pytest.raises(InvalidInput):
        validate_references(database, collection, document)


def test_active_case_query_has_an_indexed_sort_plan(database):
    query = {"student_id": fixture_id("student_a"), "archive_state": "active"}
    explanation = database.command(
        "explain",
        {
            "find": "cases",
            "filter": query,
            "sort": {"updated_at": -1, "_id": -1},
            "limit": 20,
            "hint": "cases_v1_6",
            "maxTimeMS": 1500,
        },
        verbosity="executionStats",
    )
    plan = explanation["queryPlanner"]["winningPlan"]

    def stages(node):
        if isinstance(node, dict):
            yield node.get("stage")
            for value in node.values():
                yield from stages(value)
        elif isinstance(node, list):
            for value in node:
                yield from stages(value)

    observed = set(stages(plan))
    assert "IXSCAN" in observed and "COLLSCAN" not in observed and "SORT" not in observed
    assert explanation["executionStats"]["nReturned"] == 2
    assert database.cases.index_information()["cases_v1_6"]["key"] == [
        ("student_id", 1),
        ("archive_state", 1),
        ("updated_at", -1),
        ("_id", -1),
    ]
