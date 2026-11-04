"""Workspace cookie/state binding and legacy compatibility at the HTTP boundary."""

import os

import pytest
from flask import redirect, session

from app import create_app
from app.auth.sessions import token_hash
from app.services.accounts import LOCAL_ISSUER

pytestmark = [
    pytest.mark.runtime,
    pytest.mark.skipif(os.getenv("RUN_RUNTIME") != "1", reason="Isolated local database"),
]


@pytest.fixture
def workspace_app(bundle, config):
    db, uid = bundle
    app = create_app({**config, "OIDC_ISSUER": LOCAL_ISSUER})
    app.extensions["mongo"].close()
    app.extensions["mongo"] = db.client

    @app.get("/_test/session/<actor>")
    def test_session(actor):
        session.rotate(user_id=uid(actor))
        session["context"] = "student" if actor == "student_a" else "staff"
        return "Synthetic test session created"

    yield app


def test_shared_cookie_jar_scope_binding_and_independent_logout(bundle, workspace_app):
    db, _ = bundle
    c = workspace_app.test_client()
    c.get("/student/_test/session/student_a")
    c.get("/university/_test/session/manager_finance")
    student = c.get_cookie("support_session_student", path="/student").value
    staff = c.get_cookie("support_session_university", path="/university").value
    assert student != staff
    assert b"Welcome, Student A" in c.get("/student/account").data
    assert b"Welcome, Manager Finance" in c.get("/university/account").data
    c.set_cookie("support_session_university", student, path="/university")
    response = c.get("/university/account")
    assert response.status_code == 302 and response.location.startswith("/university/sign-in")
    assert not db.sessions.find_one({"token_hash": token_hash(staff)}).get("revoked_at")
    c.set_cookie("support_session_university", staff, path="/university")
    assert b"Welcome, Manager Finance" in c.get("/university/account").data
    assert b"Welcome, Student A" in c.get("/student/account").data


def test_workspace_does_not_inherit_legacy_cookie_or_grant_role(workspace_app):
    c = workspace_app.test_client()
    c.get("/_test/session/student_a")
    assert c.get("/account").status_code == 200
    assert c.get("/university/account").status_code == 302
    c.get("/university/_test/session/student_a")
    assert c.get("/university/access").status_code == 403
    assert c.get("/university/staff").status_code == 403
    assert c.get("/universityevil/account").status_code == 404
    assert c.get("/account").status_code == 200


def test_oidc_callback_and_safe_return_stay_in_workspace(bundle, workspace_app, monkeypatch):
    db, uid = bundle
    app = workspace_app
    observed = {}

    def authorise(uri, **kwargs):
        observed.update(uri=uri, **kwargs)
        return redirect("https://identity.example/authorise")

    monkeypatch.setattr(app.extensions["university_oidc"], "authorize_redirect", authorise)
    c = app.test_client()
    assert c.get("/student/sign-in?next=/account/profile").status_code == 302
    assert observed == {"uri": "http://127.0.0.1:5000/student/auth/callback", "prompt": "login"}
    subject = db.users.find_one({"_id": uid("student_a")})["identity_subject"]
    monkeypatch.setattr(
        app.extensions["university_oidc"],
        "authorize_access_token",
        lambda **kwargs: {"userinfo": {"sub": subject}},
    )
    response = c.get("/student/auth/callback?state=synthetic&code=synthetic")
    assert response.status_code == 302 and response.location == "/student/account/profile"
    assert c.get("/student/account/profile").status_code == 200
    assert c.get("/account").status_code == 302
    observed.clear()
    assert c.get("/student/account/reauthenticate").status_code == 302
    assert observed == {
        "uri": "http://127.0.0.1:5000/student/auth/callback",
        "prompt": "login",
        "max_age": 0,
    }
