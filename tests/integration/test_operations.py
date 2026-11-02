import os
import time
from datetime import timedelta
from pathlib import Path

import pytest
from cryptography.fernet import Fernet, InvalidToken
from dotenv import dotenv_values

from app import create_app
from app.operations.recovery import capture, reconcile, restore
from app.repositories.core import utc_now
from app.repositories.schema import SCHEMAS, install_schema
from app.services.lifecycle import POLICY, Lifecycle
from scripts.database_setup import local_client

pytestmark = [
    pytest.mark.runtime,
    pytest.mark.skipif(os.getenv("RUN_RUNTIME") != "1", reason="Local operations only"),
]
VALUES = Path(__file__).resolve().parents[2] / ".env"


def test_shared_rate_limit_across_two_instances(config, monkeypatch):
    values = dotenv_values(VALUES)
    clients = [local_client(values, "web_testing") for _ in range(2)]
    apps = [
        create_app({**config, "RATE_LIMIT_ENABLED": "1", "RATE_LIMIT_READ": "1"}) for _ in range(2)
    ]
    monkeypatch.setattr("app.operations.security.time.time", lambda: 1234560000)
    try:
        for app, client in zip(apps, clients, strict=True):
            app.extensions["mongo"].close()
            app.extensions["mongo"] = client
        assert apps[0].test_client().get("/cases").status_code == 302
        response = apps[1].test_client().get("/cases")
        assert response.status_code == 429 and response.headers["Retry-After"] == "60"
    finally:
        with local_client(values, "testing") as client:
            client.student_support_test.rate_limits.delete_many({})
        for client in clients:
            client.close()


def test_encrypted_restore_replays_latest_disposal_and_suppresses_sessions_jobs(bundle, tmp_path):
    db, uid = bundle
    values = dotenv_values(VALUES)
    key = Fernet.generate_key()
    backup = tmp_path / "snapshot.enc"
    ledger = tmp_path / "ledger.enc"
    start = time.monotonic()
    metadata = capture(db, key, backup)
    assert b"Synthetic support" not in backup.read_bytes()
    lifecycle = Lifecycle(db)
    db.cases.update_one(
        {"_id": uid("case_a")},
        {
            "$set": {
                "status": "Closed",
                "archive_state": "archived",
                "closed_at": utc_now() - timedelta(days=2),
            }
        },
    )
    record = lifecycle.request(
        uid("administrator"), "admin", uid("case_a"), POLICY, "Synthetic restore replay"
    )
    lifecycle.approve(uid("approver"), "admin", record)
    lifecycle.execute(record)
    capture(db, key, ledger, True)
    with local_client(values, "schema") as schema:
        install_schema(schema.student_support_restore_test)
    with local_client(values, "restore") as client:
        target = client.student_support_restore_test
        for name in SCHEMAS:
            target[name].delete_many({})
        try:
            outcome = restore(target, key, backup, ledger)
            assert not target.cases.find_one({"_id": uid("case_a")})
            assert target.cases.find_one({"_id": uid("case_b")})
            assert outcome["sessions"] == 0 and outcome["pending_notifications"] == 0
            assert target.disposal_records.find_one({"_id": record})["state"] == "completed"
            # Recovery replay is idempotent after interruption.
            reconcile(target, list(db.disposal_records.find({"state": "completed"})))
            with pytest.raises(ValueError):
                restore(target, key, backup, ledger)
            with pytest.raises(InvalidToken):
                restore(target, Fernet.generate_key(), backup, ledger)
        finally:
            for name in SCHEMAS:
                target[name].delete_many({})
    report = {
        "elapsed_seconds": round(time.monotonic() - start, 3),
        **metadata,
        "sessions_invalidated": True,
        "disposal_replayed": True,
        "notifications_suppressed": True,
    }
    Path("runtime/recovery-observation.json").write_text(__import__("json").dumps(report, indent=2))
