import os
import re
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import dotenv_values

from app import create_app
from app.auth.sessions import COOKIE, token_hash
from app.repositories.core import utc_now
from app.services.accounts import LOCAL_ISSUER, Accounts
from app.services.audit import AuditWriter
from app.services.policy import AccessDenied
from app.services.transactions import VersionConflict
from scripts.database_setup import local_client

pytestmark = [
    pytest.mark.runtime,
    pytest.mark.skipif(os.getenv("RUN_RUNTIME") != "1", reason="Local MongoDB"),
]


@pytest.fixture
def web_app(bundle, config):
    db, uid = bundle
    web = local_client(dotenv_values(Path(__file__).resolve().parents[2] / ".env"), "web_testing")
    app = create_app(config)
    app.extensions["mongo"].close()
    app.extensions["mongo"] = web
    raw = secrets.token_urlsafe(32)
    now = utc_now()
    db.sessions.insert_one(
        {
            "_id": str(uuid4()),
            "user_id": uid("student_a"),
            "token_hash": token_hash(raw),
            "created_at": now,
            "last_seen_at": now,
            "idle_expires_at": now + timedelta(minutes=30),
            "absolute_expires_at": now + timedelta(hours=8),
            "authentication_time": now,
            "version": 0,
            "data": {"context": "student"},
        }
    )
    browser = app.test_client()
    browser.set_cookie(COOKIE, raw)
    yield app, browser
    web.close()


def form(client):
    response = client.get("/account/profile")
    assert response.status_code == 200
    return {
        key: re.search(rf'name="{key}" value="([^"]+)"'.encode(), response.data)[1].decode()
        for key in ["csrf_token", "version"]
    }


def test_own_profile_http_validation_csrf_conflict_and_role_isolation(bundle, web_app):
    db, uid = bundle
    app, client = web_app
    original = db.users.find_one({"_id": uid("student_a")})
    other = db.users.find_one({"_id": uid("student_b")})
    data = {
        **form(client),
        "display_name": "Demo <script>alert(1)</script>",
        "course_label": "Fictional computing",
    }
    assert (
        client.post(
            "/account/profile", data={k: v for k, v in data.items() if k != "csrf_token"}
        ).status_code
        == 400
    )
    assert (
        client.post("/account/profile", data={**data, "global_roles": "administrator"}).status_code
        == 400
    )
    assert (
        client.post("/account/profile", data={**data, "target": uid("student_b")}).status_code
        == 400
    )
    assert client.post("/account/profile", data=data).status_code == 303
    shown = client.get("/account/profile")
    assert b"&lt;script&gt;" in shown.data and b"<script>alert" not in shown.data
    user = db.users.find_one({"_id": uid("student_a")})
    assert (
        user["global_roles"] == original["global_roles"]
        and user["identity_subject"] == original["identity_subject"]
    )
    assert db.users.find_one({"_id": uid("student_b")}) == other
    assert client.post("/account/profile", data=data).status_code == 409
    invalid = {**form(client), "display_name": "   ", "course_label": ""}
    assert client.post("/account/profile", data=invalid).status_code == 400
    assert db.users.find_one({"_id": uid("student_a")})["display_name"] == user["display_name"]
    assert (
        client.post(
            "/account/profile",
            data={**form(client), "display_name": "Demo Student", "course_label": ""},
        ).status_code
        == 303
    )
    assert "course_label" not in db.users.find_one({"_id": uid("student_a")})
    assert not any(
        "Demo" in str(a)
        for a in db.audit_events.find({"action": "profile_updated", "actor_id": uid("student_a")})
    )
    assert app.test_client().get("/account/profile").status_code == 302
    assert app.test_client().get("/register").status_code == 404


def test_profile_write_rolls_back_on_audit_failure_and_denies_disabled(bundle, monkeypatch):
    db, uid = bundle
    svc = Accounts(db, {"IDENTITY_FINGERPRINT_KEY": "service-account-test-key-" * 3})
    before = db.users.find_one({"_id": uid("student_a")})

    def fail(*args, **kwargs):
        raise RuntimeError("Synthetic audit failure")

    monkeypatch.setattr(AuditWriter, "append", fail)
    with pytest.raises(RuntimeError):
        svc.update(uid("student_a"), 0, {"display_name": "Changed", "course_label": ""})
    assert db.users.find_one({"_id": uid("student_a")}) == before
    db.users.update_one({"_id": uid("student_a")}, {"$set": {"account_status": "disabled"}})
    with pytest.raises(AccessDenied):
        svc.update(uid("student_a"), 0, {"display_name": "Changed", "course_label": ""})


def test_simultaneous_profile_updates_have_one_conflict(bundle):
    db, uid = bundle

    def update(name):
        try:
            Accounts(db).update(uid("student_a"), 0, {"display_name": name, "course_label": ""})
            return "saved"
        except VersionConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, ["Demo One", "Demo Two"]))
    assert sorted(results) == ["conflict", "saved"]


def test_verified_enrolment_is_student_only_repeat_safe_and_never_reactivates(bundle):
    db, uid = bundle
    # Use independent identities so the shared fixture reset remains strict.
    subject = "synthetic-new-" + uuid4().hex
    svc = Accounts(db, {"IDENTITY_FINGERPRINT_KEY": "service-account-test-key-" * 3})
    claims = {
        "sub": subject,
        "name": "Demo New Student",
        "roles": ["administrator"],
        "groups": ["manager"],
        "email": "never-use@example.com",
        "student_reference": uid("student_b"),
    }
    ids = []
    try:
        with pytest.raises(AccessDenied):
            svc.resolve(LOCAL_ISSUER, claims)
        with pytest.raises(AccessDenied):
            svc.resolve("https://unapproved.invalid", claims, allow_registration=True)
        with ThreadPoolExecutor(max_workers=2) as pool:
            users = list(
                pool.map(
                    lambda _: svc.resolve(LOCAL_ISSUER, claims, allow_registration=True), range(2)
                )
            )
        ids = [u["_id"] for u in users]
        assert ids[0] == ids[1]
        user = users[0]
        assert user["global_roles"] == ["student"] and user["verified_contact"].endswith(
            "@example.invalid"
        )
        assert user["student_reference"].startswith("DEMO-") and "password" not in user
        assert (
            db.audit_events.count_documents({"actor_id": user["_id"], "action": "account_created"})
            == 1
        )
        db.users.update_one({"_id": user["_id"]}, {"$set": {"account_status": "disabled"}})
        with pytest.raises(AccessDenied):
            svc.resolve(LOCAL_ISSUER, claims, allow_registration=True)
    finally:
        found = [u["_id"] for u in db.users.find({"identity_subject": subject}, {"_id": 1})]
        db.audit_events.delete_many({"actor_id": {"$in": found}})
        db.users.delete_many({"_id": {"$in": found}})


def test_registration_start_creates_only_oidc_state(web_app, monkeypatch):
    app, _ = web_app
    app.config["SELF_REGISTRATION_ENABLED"] = True
    client = app.test_client()
    page = client.get("/register")
    assert page.status_code == 200
    assert b"/register/start" in page.data
    seen = {}

    def authorise(uri, **kwargs):
        seen.update(kwargs)
        return "provider start", 302

    monkeypatch.setattr(app.extensions["university_oidc"], "authorize_redirect", authorise)
    assert client.get("/register/start").status_code == 302
    assert seen == {"prompt": "create"}


def test_delete_http_requires_csrf_explicit_confirmation_and_fresh_authentication(bundle, web_app):
    db, uid = bundle
    app, client = web_app
    data = {**form(client), "confirmation": "DELETE"}
    assert client.get("/account/delete").status_code == 200
    assert (
        client.post(
            "/account/delete", data={k: v for k, v in data.items() if k != "csrf_token"}
        ).status_code
        == 400
    )
    assert client.post("/account/delete", data=data).status_code == 400
    assert db.users.find_one({"_id": uid("student_a")})["account_status"] == "active"
    assert not db.account_closures.find_one({"user_id": uid("student_a")})


@pytest.mark.parametrize("invalid", ["stale", "future", "different_user", "missing"])
def test_reauthentication_rejects_stale_or_wrong_identity(bundle, web_app, monkeypatch, invalid):
    db, uid = bundle
    app, client = web_app
    user = db.users.find_one({"_id": uid("student_a")})
    app.config["OIDC_ISSUER"] = user["identity_issuer"]
    requested = {}

    def begin(uri, **kwargs):
        requested.update(kwargs)
        return "Provider authentication", 302

    monkeypatch.setattr(app.extensions["university_oidc"], "authorize_redirect", begin)
    assert client.get("/account/reauthenticate").status_code == 302
    assert requested == {"prompt": "login", "max_age": 0}
    claims = {"sub": user["identity_subject"], "auth_time": int(utc_now().timestamp())}
    if invalid == "stale":
        claims["auth_time"] -= 3600
    if invalid == "future":
        claims["auth_time"] += 3600
    if invalid == "different_user":
        claims["sub"] = db.users.find_one({"_id": uid("student_b")})["identity_subject"]
    if invalid == "missing":
        claims.pop("auth_time")

    def validate(**kwargs):
        assert kwargs["claims_options"]["auth_time"]["essential"] is True
        return {"userinfo": claims}

    monkeypatch.setattr(app.extensions["university_oidc"], "authorize_access_token", validate)
    assert client.get("/auth/callback?state=synthetic&code=synthetic").status_code == 400
    assert client.get("/account/delete").status_code == 302
    assert not db.account_closures.find_one({"user_id": uid("student_a")})
