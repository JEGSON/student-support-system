import os
import secrets
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import dotenv_values

from app import create_app
from app.auth.sessions import COOKIE, token_hash
from app.repositories.core import utc_now
from app.services.audit import AuditWriter
from scripts.database_setup import local_client

pytestmark = [
    pytest.mark.runtime,
    pytest.mark.skipif(os.getenv("RUN_RUNTIME") != "1", reason="Local replica set"),
]


def test_authenticated_denial_is_attributed_and_fails_closed_if_audit_unavailable(
    bundle, config, monkeypatch
):
    db, uid = bundle
    now = utc_now()
    raw = secrets.token_urlsafe(32)
    db.sessions.insert_one(
        {
            "_id": str(uuid4()),
            "user_id": uid("student_b"),
            "token_hash": token_hash(raw),
            "created_at": now,
            "last_seen_at": now,
            "idle_expires_at": now + timedelta(minutes=20),
            "absolute_expires_at": now + timedelta(hours=8),
            "authentication_time": now,
            "data": {"context": "student"},
            "version": 0,
        }
    )
    app = create_app(config)
    app.extensions["mongo"].close()
    web = local_client(dotenv_values(Path(__file__).resolve().parents[2] / ".env"), "web_testing")
    app.extensions["mongo"] = web
    client = app.test_client()
    client.set_cookie(COOKIE, raw)
    response = client.get("/cases/" + uid("case_a"))
    assert response.status_code == 404
    event = db.audit_events.find_one({"actor_id": uid("student_b"), "action": "access_denied"})
    assert event["outcome"] == "denied" and event["request_id"] == response.headers["X-Request-ID"]
    assert "description" not in event and "body" not in event

    def unavailable(*args, **kwargs):
        raise RuntimeError("Synthetic audit outage")

    monkeypatch.setattr(AuditWriter, "append", unavailable)
    assert client.get("/cases/" + uid("case_a")).status_code == 404
    web.close()
