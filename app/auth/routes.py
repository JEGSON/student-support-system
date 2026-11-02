"""OIDC identity, current context and opaque server-session routes."""

from functools import wraps
from urllib.parse import unquote, urlsplit

from flask import Blueprint, current_app, g, redirect, render_template, request, session, url_for

from app.repositories.core import utc_now

identity = Blueprint("identity", __name__)


def safe_return_path(value):
    if not isinstance(value, str) or len(value) > 200:
        return "/account"
    decoded = unquote(unquote(value))
    try:
        url = urlsplit(decoded)
    except ValueError:
        return "/account"
    if (
        url.scheme
        or url.netloc
        or url.query
        or url.fragment
        or "\\" in decoded
        or any(ord(c) < 32 for c in decoded)
    ):
        return "/account"
    return decoded if decoded in {"/account", "/access"} else "/account"


def available_contexts(database, user, db_session=None):
    contexts = []
    roles = set(user["global_roles"])
    if "student" in roles:
        contexts.append("student")
    memberships = list(
        database.memberships.find({"user_id": user["_id"], "active": True}, session=db_session)
    )
    if any(
        database.teams.find_one({"_id": m["team_id"], "active": True}, session=db_session)
        for m in memberships
    ):
        contexts.append("staff")
    if roles & {"administrator", "access_approver"}:
        contexts.append("admin")
    if "audit_reviewer" in roles:
        contexts.append("audit")
    return contexts


def authenticated(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.storage_failed:
            return render_template(
                "error.html",
                title="Sign-in service unavailable",
                message="Please try again.",
                context="public",
            ), 503
        if not g.user:
            return redirect(url_for("identity.sign_in", next=safe_return_path(request.path)))
        return view(*args, **kwargs)

    return wrapped


@identity.get("/sign-in")
def sign_in():
    if g.user:
        return redirect(url_for("identity.account"))
    if session.storage_failed:
        return "Sign-in service unavailable. Please try again.", 503
    session.rotate()
    session["context"] = safe_return_path(request.args.get("next"))
    try:
        client = current_app.extensions["university_oidc"]
        return client.authorize_redirect(
            current_app.config["APP_BASE_URL"].rstrip("/") + "/auth/callback"
        )
    except Exception:
        session.logout()
        current_app.logger.warning("identity_start_failed")
        return render_template(
            "error.html",
            title="Sign-in is temporarily unavailable",
            message="Please try again.",
            context="public",
        ), 503


@identity.get("/auth/callback")
def callback():
    try:
        if len(request.args.getlist("state")) != 1 or len(request.args.getlist("code")) != 1:
            raise ValueError("Invalid response.")
        issuer = current_app.config["OIDC_ISSUER"].rstrip("/")
        options = {
            "iss": {"essential": True, "value": issuer},
            "aud": {"essential": True, "value": current_app.config["OIDC_CLIENT_ID"]},
            "sub": {"essential": True},
            "exp": {"essential": True},
            "iat": {"essential": True},
            "nonce": {"essential": True},
        }
        if current_app.config.get("OIDC_REQUIRED_ACR"):
            options["acr"] = {"essential": True, "value": current_app.config["OIDC_REQUIRED_ACR"]}
        token = current_app.extensions["university_oidc"].authorize_access_token(
            claims_options=options, leeway=0
        )
        claims = token.get("userinfo")
        if not claims or not isinstance(claims.get("sub"), str):
            raise ValueError("Verified identity required.")
        database = current_app.extensions["mongo"][current_app.config["MONGODB_DATABASE"]]
        user = database.users.find_one(
            {
                "identity_issuer": issuer,
                "identity_subject": claims["sub"],
                "account_status": "active",
            }
        )
        if not user:
            raise ValueError("Account is unavailable.")
        destination = safe_return_path(session.get("context"))
        session.rotate(user_id=user["_id"], authentication_time=utc_now())
        contexts = available_contexts(database, user)
        if len(contexts) == 1:
            session["context"] = contexts[0]
        return redirect(destination)
    except Exception:
        session.logout()
        current_app.logger.warning("identity_response_rejected")
        return render_template(
            "error.html",
            title="We could not sign you in",
            message="Your sign-in response was invalid, expired or your account is unavailable. Start sign-in again.",
            context="public",
        ), 400


@identity.get("/account")
@authenticated
def account():
    database = current_app.extensions["mongo"][current_app.config["MONGODB_DATABASE"]]
    contexts = available_contexts(database, g.user)
    if session.get("context") not in contexts:
        session.pop("context", None)
    return render_template(
        "auth/account.html",
        title="Your account",
        context=session.get("context", "Choose a context"),
        contexts=contexts,
    )


@identity.post("/account/context")
@authenticated
def choose_context():
    if set(request.form) - {"csrf_token", "context"} or any(
        len(request.form.getlist(key)) != 1 for key in request.form
    ):
        return "Invalid request.", 400
    database = current_app.extensions["mongo"][current_app.config["MONGODB_DATABASE"]]
    context = request.form.get("context")
    if context not in available_contexts(database, g.user):
        return "Access denied.", 403
    auth_time = session.authentication_time
    session.rotate(user_id=g.user["_id"], authentication_time=auth_time, preserve_absolute=True)
    session["context"] = context
    return redirect(url_for("identity.account"))


@identity.post("/sign-out")
@authenticated
def sign_out():
    session.logout()
    return render_template("auth/signed_out.html", title="Signed out", context="public")
