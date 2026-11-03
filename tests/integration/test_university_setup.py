import os
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import dotenv_values

from app.operations.bootstrap import bootstrap_service
from app.repositories.core import utc_now
from app.repositories.schema import SCHEMAS, install_schema
from app.services.lifecycle import Lifecycle
from app.services.policy import AccessDenied
from app.services.student_cases import StudentCases
from app.services.teams import Teams
from app.services.transactions import VersionConflict
from scripts.database_setup import local_client

pytestmark = [
    pytest.mark.runtime,
    pytest.mark.skipif(os.getenv("RUN_RUNTIME") != "1", reason="Local replica set"),
]


def test_database_intake_routing_and_team_history_guards(bundle):
    db, uid = bundle
    svc = Teams(db)
    newteams = []
    try:
        with pytest.raises(AccessDenied):
            svc.save(uid("student_a"), "student", "Forbidden", ["finance"], [])
        key = svc.save(
            uid("administrator"),
            "admin",
            "University intake " + uuid4().hex,
            ["finance"],
            ["finance"],
        )
        newteams.append(key)
        case = StudentCases(db, {}, "database").create(
            uid("student_a"), "student", "finance", "Synthetic routed request", uuid4().hex * 2
        )
        saved = db.cases.find_one({"_id": case["_id"] if isinstance(case, dict) else case})
        assert saved["team_id"] == key
        current = db.teams.find_one({"_id": key})
        with pytest.raises(ValueError):
            svc.save(
                uid("administrator"),
                "admin",
                current["name"],
                ["finance"],
                [],
                team=key,
                version=current["authorization_revision"],
                active=False,
            )
        with pytest.raises(ValueError):
            svc.save(
                uid("administrator"), "admin", "Duplicate " + uuid4().hex, ["finance"], ["finance"]
            )
        with pytest.raises(VersionConflict):
            svc.save(
                uid("administrator"),
                "admin",
                current["name"],
                ["finance"],
                ["finance"],
                team=key,
                version=-1,
            )
    finally:
        for key in newteams:
            cases = [r["_id"] for r in db.cases.find({"team_id": key}, {"_id": 1})]
            for name in ["messages", "internal_notes", "case_events", "notification_outbox"]:
                db[name].delete_many({"case_id": {"$in": cases}})
            db.submission_keys.delete_many({"result_id": {"$in": cases}})
            db.cases.delete_many({"team_id": key})
            db.teams.delete_one({"_id": key})


def test_approved_category_retention_durations_and_holds(bundle):
    db, uid = bundle
    settings = {
        "SERVICE_POLICY_APPROVED": True,
        "RETENTION_POLICY_REFERENCE": "UNIT-POLICY-V1",
        "RETENTION_DAYS": {"finance": 30},
    }
    svc = Lifecycle(db, settings)
    db.cases.update_one(
        {"_id": uid("case_a")},
        {
            "$set": {
                "status": "Closed",
                "archive_state": "archived",
                "closed_at": utc_now() - timedelta(days=5),
            }
        },
    )
    with pytest.raises(AccessDenied):
        svc.request(uid("administrator"), "admin", uid("case_a"), "UNIT-POLICY-V1", "Too recent")
    db.cases.update_one(
        {"_id": uid("case_a")}, {"$set": {"closed_at": utc_now() - timedelta(days=31)}}
    )
    record = svc.request(
        uid("administrator"),
        "admin",
        uid("case_a"),
        "UNIT-POLICY-V1",
        "Approved test retention rule",
    )
    svc.approve(uid("approver"), "admin", record)
    svc.hold(uid("administrator"), "admin", uid("case_a"), True, "Hold blocks erasure")
    with pytest.raises(AccessDenied):
        svc.execute(record)
    svc.hold(uid("administrator"), "admin", uid("case_a"), False, "Reviewed release")
    svc.execute(record)
    assert not db.cases.find_one({"_id": uid("case_a")})
    assert db.disposal_records.find_one({"_id": record})["policy"] == "UNIT-POLICY-V1"


def test_bootstrap_uses_independent_identities_and_cannot_repeat():
    values = dotenv_values(Path(__file__).resolve().parents[2] / ".env")
    with local_client(values, "schema") as schema:
        install_schema(schema.student_support_restore_test)
    with local_client(values, "restore") as client:
        db = client.student_support_restore_test
        if any(db[name].find_one({}) for name in SCHEMAS):
            pytest.fail("Dedicated bootstrap quarantine must be empty")
        admin = {
            "subject": "bootstrap-admin",
            "name": "University administrator",
            "verified_contact": "admin@example.invalid",
        }
        approver = {
            "subject": "bootstrap-approver",
            "name": "Independent approver",
            "verified_contact": "approver@example.invalid",
        }
        try:
            with pytest.raises(ValueError):
                bootstrap_service(db, "https://identity.example.invalid", admin, admin)
            result = bootstrap_service(db, "https://identity.example.invalid", admin, approver)
            assert db.users.find_one({"_id": result["administrator_id"]})["global_roles"] == [
                "administrator"
            ]
            assert db.users.find_one({"_id": result["approver_id"]})["global_roles"] == [
                "access_approver"
            ]
            assert db.service_principals.find_one({"_id": result["notification_principal_id"]})[
                "active"
            ]
            with pytest.raises(AccessDenied):
                bootstrap_service(db, "https://identity.example.invalid", admin, approver)
            assert db.users.count_documents({}) == 2
        finally:
            for name in SCHEMAS:
                db[name].delete_many({})
