"""Actual MongoDB-backed opaque session checks; JWT checks live in unit tests."""

import os
import secrets
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import dotenv_values
from flask import g, session

from app import create_app
from app.auth.sessions import COOKIE, token_hash
from app.repositories.core import utc_now
from app.repositories.fixtures import fixture_id
from scripts.database_setup import local_client

pytestmark = [
    pytest.mark.runtime,
    pytest.mark.skipif(os.getenv("RUN_RUNTIME") != "1", reason="Isolated replica set required"),
]


@pytest.fixture
def identity_app(config):
    values = dotenv_values(Path(__file__).resolve().parents[2] / ".env")
    client = local_client(values, "testing")
    application = create_app(config)
    application.extensions["mongo"].close()
    application.extensions["mongo"] = client

    @application.get("/test-rotate")
    def rotate():
        session.rotate(user_id=fixture_id("student_a"), authentication_time=utc_now())
        session["context"] = "student"
        return "rotated"

    request_ids = []

    @application.after_request
    def track_test_request(response):
        request_ids.append(g.request_id)
        return response

    try:
        yield application
    finally:
        client.student_support_test.audit_events.delete_many({"request_id": {"$in": request_ids}})
        client.close()


def test_opaque_rotation_csrf_logout_and_replay(identity_app):
    app = identity_app
    db = app.extensions["mongo"][app.config["MONGODB_DATABASE"]]
    client = app.test_client()
    assert client.get("/account").status_code == 302
    response = client.get("/test-rotate")
    raw = client.get_cookie(COOKIE).value
    assert (
        len(raw) == 43
        and "HttpOnly" in response.headers["Set-Cookie"]
        and "SameSite=Lax" in response.headers["Set-Cookie"]
    )
    record = db.sessions.find_one({"token_hash": token_hash(raw)})
    assert record and raw not in str(record) and record["user_id"] == fixture_id("student_a")
    response = client.get("/account")
    assert response.status_code == 200
    import re

    csrf = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)[1].decode()
    assert client.post("/sign-out").status_code == 400
    assert (
        client.post("/account/context", data={"csrf_token": csrf, "context": "admin"}).status_code
        == 403
    )
    assert (
        client.post(
            "/account/context",
            data={"csrf_token": csrf, "context": "student", "global_roles": "administrator"},
        ).status_code
        == 400
    )
    assert (
        client.post("/account/context", data={"csrf_token": csrf, "context": "student"}).status_code
        == 302
    )
    newer = client.get_cookie(COOKIE).value
    assert newer != raw and db.sessions.find_one({"token_hash": token_hash(raw)})["revoked_at"]
    assert (
        db.sessions.find_one({"token_hash": token_hash(newer)})["absolute_expires_at"]
        == record["absolute_expires_at"]
    )
    replay = app.test_client()
    replay.set_cookie(COOKIE, raw)
    assert replay.get("/account").status_code == 302
    response = client.get("/account")
    csrf = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)[1].decode()
    assert client.post("/sign-out", data={"csrf_token": csrf}).status_code == 200
    assert client.get_cookie(COOKIE) is None
    replay.set_cookie(COOKIE, newer)
    assert replay.get("/account").status_code == 302


@pytest.mark.parametrize("expiry", ["idle_expires_at", "absolute_expires_at"])
def test_expired_cookie_is_denied(identity_app, expiry):
    client = identity_app.test_client()
    client.get("/test-rotate")
    raw = client.get_cookie(COOKIE).value
    db = identity_app.extensions["mongo"].student_support_test
    db.sessions.update_one(
        {"token_hash": token_hash(raw)}, {"$set": {expiry: utc_now() - timedelta(seconds=1)}}
    )
    assert client.get("/account").status_code == 302


def test_disable_takes_effect_next_request(identity_app):
    db = identity_app.extensions["mongo"].student_support_test
    # Dedicated account avoids altering shared synthetic identities.
    original = db.users.find_one({"_id": fixture_id("student_a")})
    user = {
        **original,
        "_id": str(uuid4()),
        "identity_subject": "session-disable-" + secrets.token_hex(8),
    }
    user.pop("student_reference", None)
    db.users.insert_one(user)
    token = secrets.token_urlsafe(32)
    now = utc_now()
    db.sessions.insert_one(
        {
            "_id": str(uuid4()),
            "token_hash": token_hash(token),
            "user_id": user["_id"],
            "created_at": now,
            "last_seen_at": now,
            "idle_expires_at": now + timedelta(minutes=20),
            "absolute_expires_at": now + timedelta(hours=8),
            "authentication_time": now,
            "fixture_version": "synthetic-v1",
            "data": {},
            "version": 0,
        }
    )
    client = identity_app.test_client()
    client.set_cookie(COOKIE, token)
    assert client.get("/account").status_code == 200
    db.users.update_one({"_id": user["_id"]}, {"$set": {"account_status": "disabled"}})
    assert client.get("/account").status_code == 302
    assert db.sessions.find_one({"token_hash": token_hash(token)})["revoked_at"]
    db.users.delete_one({"_id": user["_id"]})


def test_production_cookie_flags_and_idle_limit(identity_app):
    identity_app.config["SESSION_COOKIE_SECURE"] = True
    client = identity_app.test_client()
    response = client.get("/test-rotate", base_url="https://localhost")
    cookie = response.headers["Set-Cookie"]
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=Lax" in cookie
    from http.cookies import SimpleCookie

    parsed = SimpleCookie()
    parsed.load(cookie)
    raw = parsed[COOKIE].value
    record = identity_app.extensions["mongo"].student_support_test.sessions.find_one(
        {"token_hash": token_hash(raw)}
    )
    assert record["idle_expires_at"] - record["created_at"] == timedelta(minutes=30)
    assert record["absolute_expires_at"] - record["created_at"] == timedelta(hours=8)


@pytest.mark.parametrize(
    "actor,expected", [("student_a", 302), ("disabled", 400), ("unmapped", 400)]
)
def test_verified_subject_mapping_ignores_provider_roles(
    identity_app, monkeypatch, actor, expected
):
    db = identity_app.extensions["mongo"].student_support_test
    actual = db.users.find_one({"_id": fixture_id("student_a" if actor == "unmapped" else actor)})
    identity_app.config["OIDC_ISSUER"] = actual["identity_issuer"]
    # The OIDC signature/claim boundary is tested separately with real signed JWTs
    # and real Keycloak; this test isolates mapping after that verification.
    subject = "not-provisioned" if actor == "unmapped" else actual["identity_subject"]
    monkeypatch.setattr(
        identity_app.extensions["university_oidc"],
        "authorize_access_token",
        lambda **kwargs: {
            "userinfo": {"sub": subject, "roles": ["administrator"], "groups": ["access_approver"]}
        },
    )
    client = identity_app.test_client()
    response = client.get("/auth/callback?state=synthetic&code=synthetic")
    assert response.status_code == expected
    if expected == 302:
        raw = client.get_cookie(COOKIE).value
        record = db.sessions.find_one({"token_hash": token_hash(raw)})
        assert record["user_id"] == fixture_id("student_a") and record["data"] == {
            "context": "student"
        }
        assert db.users.find_one({"_id": record["user_id"]})["global_roles"] == ["student"]
    else:
        assert client.get_cookie(COOKIE) is None
