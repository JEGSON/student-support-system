from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import dotenv_values

from app.repositories.fixtures import fixture_documents, fixture_id
from scripts.database_setup import local_client


@pytest.fixture
def bundle():
    values = dotenv_values(Path(__file__).resolve().parents[2] / ".env")
    client = local_client(values, "testing")
    db = client.student_support_test
    documents = fixture_documents(values["OIDC_ISSUER"])
    ids = {d["_id"]: str(uuid4()) for docs in documents.values() for d in docs}
    suffix = uuid4().hex

    def translate(value):
        if isinstance(value, dict):
            return {k: translate(v) for k, v in value.items()}
        if isinstance(value, list):
            return [translate(v) for v in value]
        if isinstance(value, str):
            return ids.get(value, value)
        return value

    for collection, docs in documents.items():
        for original in docs:
            doc = {**translate(original), "fixture_version": "synthetic-v1"}
            for field in ["identity_subject", "student_reference", "name", "reference"]:
                if field in doc:
                    doc[field] = (
                        ("T-" + doc["_id"]) if field == "reference" else doc[field] + suffix
                    )
            db[collection].insert_one(doc)

    def uid(label):
        return ids[fixture_id(label)]

    yield db, uid
    case_ids = [
        r["_id"] for r in db.cases.find({"student_id": {"$in": list(ids.values())}}, {"_id": 1})
    ]
    for name in [
        "case_events",
        "messages",
        "internal_notes",
        "notification_outbox",
        "triage_claims",
    ]:
        db[name].delete_many({"case_id": {"$in": case_ids}})
    db.cases.delete_many({"_id": {"$in": case_ids}})
    db.submission_keys.delete_many({"user_id": {"$in": list(ids.values())}})
    db.sessions.delete_many({"user_id": {"$in": list(ids.values())}})
    for name in documents:
        db[name].delete_many({"_id": {"$in": list(ids.values())}})
    db.privileged_grants.delete_many({"user_id": {"$in": list(ids.values())}})
    db.triage_claims.delete_many({"case_id": {"$in": list(ids.values())}})
    db.audit_events.delete_many({"actor_id": {"$in": list(ids.values())}})
    client.close()
