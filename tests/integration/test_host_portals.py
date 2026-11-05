"""Portal role, CSRF, login-hint and session boundaries on the real local database."""

import os
import re
from html import unescape

import pytest
from flask import redirect
from pymongo.errors import AutoReconnect

from app import create_app
from app.services.accounts import LOCAL_ISSUER

pytestmark = [
    pytest.mark.runtime,
    pytest.mark.skipif(os.getenv("RUN_RUNTIME") != "1", reason="Isolated local database"),
]


@pytest.fixture(params=["student", "university"])
def portal_app(request, bundle, config):
    database, _ = bundle
    app = create_app(
        {
            **config,
            "PORTAL_KIND": request.param,
            "OTHER_PORTAL_ORIGIN": "http://localhost:5000",
            "OIDC_ISSUER": LOCAL_ISSUER,
        }
    )
    app.extensions["mongo"].close()
    app.extensions["mongo"] = database.client
    return app


def csrf(response):
    return re.search(rb'name="csrf_token" value="([^"]+)"', response.data)[1].decode()


def test_email_entry_requires_csrf_and_passes_only_validated_hint(portal_app, monkeypatch):
    client = portal_app.test_client()
    observed = {}

    def authorise(uri, **kwargs):
        observed.update(uri=uri, **kwargs)
        return redirect("https://identity.example/authorise")

    monkeypatch.setattr(portal_app.extensions["university_oidc"], "authorize_redirect", authorise)
    assert client.get("/sign-in/continue").location == "/sign-in"
    token = csrf(client.get("/sign-in"))
    assert client.post("/sign-in", data={"email": "user@example.invalid"}).status_code == 400
    assert (
        client.post("/sign-in", data={"csrf_token": token, "email": "invalid"}).status_code == 400
    )
    response = client.post(
        "/sign-in", data={"csrf_token": token, "email": " User@Example.Invalid "}
    )
    assert response.status_code == 200 and b"user@example.invalid" in response.data
    assert client.get("/sign-in/continue").status_code == 302
    assert observed == {
        "uri": "http://127.0.0.1:5000/auth/callback",
        "prompt": "login",
        "login_hint": "user@example.invalid",
    }


@pytest.mark.parametrize("actor", ["student_a", "manager_finance"])
def test_verified_callback_requires_portal_role_and_binds_cookie(
    portal_app, bundle, monkeypatch, actor
):
    database, uid = bundle
    kind = portal_app.config["PORTAL_KIND"]
    user = database.users.find_one({"_id": uid(actor)})
    monkeypatch.setattr(
        portal_app.extensions["university_oidc"],
        "authorize_access_token",
        lambda **kwargs: {"userinfo": {"sub": user["identity_subject"]}},
    )
    client = portal_app.test_client()
    response = client.get("/auth/callback?state=verified&code=verified")
    allowed = (actor == "student_a") == (kind == "student")
    if not allowed:
        assert response.status_code == 400
        assert b"http://localhost:5000/sign-in" in response.data
        assert client.get("/account").status_code == 302
        return
    assert response.status_code == 302 and response.location == "/account"
    cookie = client.get_cookie("support_session_" + kind)
    assert cookie.path == "/" and cookie.domain == "localhost"
    assert cookie.http_only
    response = client.get("/account")
    assert response.status_code == 200 and user["display_name"].encode() in response.data
    token = csrf(response)
    forbidden_context = "staff" if kind == "student" else "student"
    assert (
        client.post(
            "/account/context", data={"csrf_token": token, "context": forbidden_context}
        ).status_code
        == 403
    )


def test_email_step_preserves_safe_return_destination(portal_app, bundle, monkeypatch):
    database, uid = bundle
    actor = "student_a" if portal_app.config["PORTAL_KIND"] == "student" else "manager_finance"
    subject = database.users.find_one({"_id": uid(actor)})["identity_subject"]
    monkeypatch.setattr(
        portal_app.extensions["university_oidc"],
        "authorize_redirect",
        lambda *args, **kwargs: redirect("https://identity.example/authorise"),
    )
    monkeypatch.setattr(
        portal_app.extensions["university_oidc"],
        "authorize_access_token",
        lambda **kwargs: {"userinfo": {"sub": subject}},
    )
    client = portal_app.test_client()
    address = "/sign-in?next=/account/profile"
    token = csrf(client.get(address))
    ready = client.post(address, data={"csrf_token": token, "email": "actor@example.invalid"})
    link = unescape(re.search(rb'href="([^"]*/sign-in/continue[^"]*)"', ready.data)[1].decode())
    assert client.get(link).status_code == 302
    response = client.get("/auth/callback?state=verified&code=verified")
    assert response.location == "/account/profile"


def test_callback_outage_is_not_reported_as_invalid_account(portal_app, monkeypatch):
    def unavailable(**kwargs):
        raise AutoReconnect("Private connection detail must not be rendered")

    monkeypatch.setattr(
        portal_app.extensions["university_oidc"], "authorize_access_token", unavailable
    )
    response = portal_app.test_client().get("/auth/callback?state=verified&code=verified")
    assert response.status_code == 503
    assert b"temporarily unavailable" in response.data
    assert b"Private connection detail" not in response.data
    assert b"approved staff account" not in response.data
