"""OIDC identity, current context and opaque server-session routes."""

from functools import wraps
from urllib.parse import unquote, urlsplit

from flask import (
    Blueprint,
    abort,
    current_app,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from pymongo.errors import PyMongoError
from requests.exceptions import RequestException

from app.auth.workspaces import callback_url, workspace_url
from app.repositories.core import utc_now
from app.services.account_privacy import AccountPrivacy
from app.services.accounts import Accounts, profile_errors
from app.services.enrolment import contact_address, invitation_hash
from app.services.policy import AccessDenied
from app.services.transactions import VersionConflict

identity = Blueprint("identity", __name__)


class PortalAccessDenied(AccessDenied):
    """A verified identity belongs in the other portal."""


@identity.errorhandler(PyMongoError)
def identity_storage_unavailable(error):
    current_app.logger.warning("identity_storage_unavailable")
    return render_template(
        "error.html",
        title="Sign-in service temporarily unavailable",
        message="Please try again shortly. Your account details have not been changed.",
        context="public",
    ), 503


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
    return (
        decoded
        if decoded in {"/account", "/access", "/account/profile", "/account/delete"}
        else "/account"
    )


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


@identity.route("/sign-in", methods=["GET", "POST"])
def sign_in():
    if current_app.config["PORTAL_KIND"] == "general":
        return start_sign_in()
    if g.user:
        return redirect(url_for("identity.account"))
    if session.storage_failed:
        abort(503)
    error = None
    if request.method == "POST":
        if set(request.form) != {"csrf_token", "email"} or any(
            len(request.form.getlist(k)) != 1 for k in request.form
        ):
            abort(400)
        try:
            hint = contact_address(request.form["email"].strip().lower())
        except ValueError:
            error = "Enter a valid email address."
        else:
            session["login_hint"] = hint
            return render_template(
                "auth/portal_sign_in.html",
                title="Continue to sign in",
                context="public",
                ready=hint,
                error=None,
                return_to=safe_return_path(request.args.get("next")),
            )
    return render_template(
        "auth/portal_sign_in.html",
        title="Staff sign-in"
        if current_app.config["PORTAL_KIND"] == "university"
        else "Student sign-in",
        context="public",
        error=error,
        return_to=safe_return_path(request.args.get("next")),
    ), 400 if error else 200


@identity.get("/sign-in/continue")
def sign_in_continue():
    hint = session.get("login_hint")
    if current_app.config["PORTAL_KIND"] == "general" or not hint:
        return redirect(url_for("identity.sign_in"))
    return start_sign_in(login_hint=hint)


def start_sign_in(registration=False, login_hint=None):
    if g.user:
        return redirect(url_for("identity.account"))
    if session.storage_failed:
        return "Sign-in service unavailable. Please try again.", 503
    pending_invitation = session.get("invitation_hash")
    session.rotate()
    if pending_invitation:
        session["invitation_hash"] = pending_invitation
    session["context"] = safe_return_path(request.args.get("next"))
    try:
        client = current_app.extensions["university_oidc"]
        return client.authorize_redirect(
            callback_url(),
            **({"prompt": "create"} if registration else {"prompt": "login"}),
            **({"login_hint": login_hint} if login_hint else {}),
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
    failure_stage = "response"
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
        reauth_user = session.get("reauth_user")
        reauth_started = session.get("reauth_started")
        if reauth_user:
            options["auth_time"] = {"essential": True}
        if current_app.config.get("OIDC_REQUIRED_ACR"):
            options["acr"] = {"essential": True, "value": current_app.config["OIDC_REQUIRED_ACR"]}
        failure_stage = "token_validation"
        token = current_app.extensions["university_oidc"].authorize_access_token(
            claims_options=options, leeway=0
        )
        claims = token.get("userinfo")
        if not claims or not isinstance(claims.get("sub"), str):
            raise ValueError("Verified identity required.")
        database = current_app.extensions["mongo"][current_app.config["MONGODB_DATABASE"]]
        failure_stage = "account_lookup"
        user = Accounts(database).resolve(
            issuer,
            claims,
            allow_registration=current_app.config["SELF_REGISTRATION_ENABLED"] and not reauth_user,
            invitation_hash=session.get("invitation_hash") if not reauth_user else None,
        )
        if not user:
            raise ValueError("Account is unavailable.")
        now = utc_now()
        if reauth_user:
            auth_time = claims.get("auth_time")
            if (
                user["_id"] != reauth_user
                or type(auth_time) is not int
                or type(reauth_started) is not int
                or not reauth_started - 5 <= auth_time <= now.timestamp() + 30
                or now.timestamp() - auth_time > 300
            ):
                raise AccessDenied("Fresh authentication for the same account is required.")
        contexts = available_contexts(database, user)
        portal = current_app.config["PORTAL_KIND"]
        if (portal == "student" and "student" not in contexts) or (
            portal == "university" and not set(contexts) & {"staff", "admin", "audit"}
        ):
            raise PortalAccessDenied("This identity is not approved for this portal.")
        destination = safe_return_path(session.get("context"))
        session.rotate(user_id=user["_id"], authentication_time=now)
        if reauth_user:
            session["reauthenticated_at"] = int(now.timestamp())
        contexts = available_contexts(database, user)
        if portal == "student":
            session["context"] = "student"
        elif portal == "university":
            session["context"] = next(c for c in ["staff", "admin", "audit"] if c in contexts)
        elif len(contexts) == 1:
            session["context"] = contexts[0]
        return redirect(request.script_root + destination)
    except PortalAccessDenied:
        session.logout()
        current_app.logger.warning("identity_wrong_portal")
        staff_portal = current_app.config["PORTAL_KIND"] == "student"
        return render_template(
            "error.html",
            title="We could not sign you in",
            context="public",
            message=(
                "This is the student portal. Staff and administrators must use the staff portal."
                if staff_portal
                else "This is the staff portal. Use the student portal for your student account."
            ),
            action_label="Open staff sign-in" if staff_portal else "Open student sign-in",
            action_url=workspace_url(
                "identity.sign_in", "university" if staff_portal else "student"
            ),
        ), 400
    except (PyMongoError, RequestException):
        session.logout()
        current_app.logger.warning("identity_dependency_unavailable stage=%s", failure_stage)
        return render_template(
            "error.html",
            title="Sign-in service temporarily unavailable",
            context="public",
            message="We could not reach the sign-in service. Please start sign-in again shortly.",
            action_label="Start sign-in again",
            action_url=url_for("identity.sign_in"),
        ), 503
    except Exception:
        session.logout()
        current_app.logger.warning("identity_response_rejected stage=%s", failure_stage)
        return render_template(
            "error.html",
            title="We could not sign you in",
            message="Your sign-in attempt expired, could not be verified, or your account is unavailable. Start sign-in again.",
            context="public",
            action_label="Start sign-in again",
            action_url=url_for("identity.sign_in"),
        ), 400


@identity.get("/account")
@authenticated
def account():
    database = current_app.extensions["mongo"][current_app.config["MONGODB_DATABASE"]]
    contexts = available_contexts(database, g.user)
    if current_app.config["PORTAL_KIND"] == "student":
        contexts = [c for c in contexts if c == "student"]
    elif current_app.config["PORTAL_KIND"] == "university":
        contexts = [c for c in contexts if c != "student"]
    if session.get("context") not in contexts:
        session.pop("context", None)
    recent = []
    if current_app.config["PORTAL_KIND"] == "student" and session.get("context") == "student":
        from app.services.student_cases import StudentCases

        recent, _ = StudentCases(
            database, current_app.config["CASE_ROUTING"], current_app.config["CASE_ROUTING_SOURCE"]
        ).list(g.user["_id"], "student")
    return render_template(
        "auth/account.html",
        title="Your account",
        context=session.get("context", "Choose a context"),
        contexts=contexts,
        recent=recent[:5],
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
    portal = current_app.config["PORTAL_KIND"]
    if (portal == "student" and context != "student") or (
        portal == "university" and context == "student"
    ):
        abort(403)
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


@identity.get("/staff/sign-in")
def staff_sign_in():
    return render_template(
        "auth/staff_sign_in.html",
        title="University staff sign-in",
        context=session.get("context", "public"),
    )


@identity.get("/register")
def register():
    if current_app.config["ENROLMENT_MODE"] == "invitation":
        return redirect(url_for("identity.join"))
    if not current_app.config["SELF_REGISTRATION_ENABLED"]:
        abort(404)
    if g.user:
        return redirect(url_for("identity.profile"))
    return render_template("auth/register.html", title="Create your account", context="public")


@identity.get("/register/start")
def register_start():
    if current_app.config["ENROLMENT_MODE"] == "invitation":
        return redirect(url_for("identity.join"))
    if not current_app.config["SELF_REGISTRATION_ENABLED"]:
        abort(404)
    return start_sign_in(registration=True)


@identity.route("/account/profile", methods=["GET", "POST"])
@authenticated
def profile():
    service = Accounts(current_app.extensions["mongo"][current_app.config["MONGODB_DATABASE"]])
    errors = {}
    status = 200
    try:
        data = service.read(g.user["_id"])
        version = data.get("profile_version", 0)
        values = {field: data.get(field, "") for field in ["display_name", "course_label"]}
        if request.method == "POST":
            if set(request.form) != {
                "csrf_token",
                "version",
                "display_name",
                "course_label",
            } or any(len(request.form.getlist(key)) != 1 for key in request.form):
                abort(400)
            values = {field: request.form[field] for field in values}
            errors = profile_errors(values)
            try:
                submitted_version = int(request.form["version"])
                if submitted_version < 0:
                    raise ValueError
            except ValueError:
                abort(400)
            if errors:
                status = 400
            else:
                try:
                    service.update(g.user["_id"], submitted_version, values)
                except VersionConflict:
                    errors["service"] = (
                        "Your profile changed in another tab. Review these details and save again."
                    )
                    status = 409
                else:
                    return redirect(url_for("identity.profile", saved="1"), code=303)
        return render_template(
            "auth/profile.html",
            title="Your profile",
            context=session.get("context", "account"),
            values=values,
            profile=data,
            version=version,
            errors=errors,
            saved=request.args.get("saved") == "1" and request.method == "GET",
        ), status
    except AccessDenied:
        abort(403)
    except PyMongoError:
        return render_template(
            "error.html",
            title="Profile temporarily unavailable",
            context="account",
            message="We could not confirm your profile. Please try again shortly.",
        ), 503


@identity.route("/join", methods=["GET", "POST"])
def join():
    if not current_app.config["REGISTRATION_AVAILABLE"]:
        abort(404)
    error = None
    if request.method == "POST":
        if set(request.form) != {"csrf_token", "code"} or any(
            len(request.form.getlist(k)) != 1 for k in request.form
        ):
            abort(400)
        try:
            digest = invitation_hash(request.form["code"].strip())
        except ValueError:
            error = "Enter the complete invitation code supplied by your university."
        else:
            session.rotate()
            session["invitation_hash"] = digest
            return redirect(url_for("identity.join_continue"), code=303)
    return render_template(
        "auth/join.html", title="Join Student Support", context="public", error=error
    ), 400 if error else 200


@identity.get("/join/continue")
def join_continue():
    if not session.get("invitation_hash"):
        return redirect(url_for("identity.join"))
    return render_template(
        "auth/join_continue.html", title="Verify your university account", context="public"
    )


@identity.get("/join/sign-in")
def join_sign_in():
    if not session.get("invitation_hash"):
        return redirect(url_for("identity.join"))
    # GET navigation preserves form-action CSP; provider owns verification/recovery.
    return start_sign_in()


@identity.get("/account/reauthenticate")
@authenticated
def reauthenticate():
    actor = g.user["_id"]
    session.rotate()
    session["reauth_user"] = actor
    session["reauth_started"] = int(utc_now().timestamp())
    session["context"] = "/account/delete"
    try:
        return current_app.extensions["university_oidc"].authorize_redirect(
            callback_url(),
            prompt="login",
            max_age=0,
        )
    except Exception:
        session.logout()
        current_app.logger.warning("reauthentication_unavailable")
        abort(503)


@identity.route("/account/delete", methods=["GET", "POST"])
@authenticated
def delete_account():
    db = current_app.extensions["mongo"][current_app.config["MONGODB_DATABASE"]]
    error = None
    status = 200
    fresh = session.get("reauthenticated_at")
    recent = type(fresh) is int and 0 <= utc_now().timestamp() - fresh <= 300
    try:
        if request.method == "POST":
            if set(request.form) != {"csrf_token", "version", "confirmation"} or any(
                len(request.form.getlist(k)) != 1 for k in request.form
            ):
                abort(400)
            if request.form["confirmation"] != "DELETE" or not recent:
                error = "Sign in again, then type DELETE to confirm."
                status = 400
            else:
                try:
                    record = AccountPrivacy(
                        db, current_app.config["IDENTITY_FINGERPRINT_KEY"]
                    ).close(g.user["_id"], int(request.form["version"]), fresh)
                except VersionConflict:
                    error, status = "Your profile changed. Review this page and try again.", 409
                except AccessDenied as problem:
                    error, status = str(problem), 403
                except ValueError:
                    abort(400)
                else:
                    session.rotate()
                    session["closure_reference"] = record["_id"]
                    session["closure_state"] = record["state"]
                    return redirect(url_for("identity.account_closed"), code=303)
        return render_template(
            "auth/delete_account.html",
            title="Delete your profile and close your account",
            context=session.get("context", "account"),
            recent=recent,
            error=error,
            version=g.user.get("profile_version", 0),
        ), status
    except PyMongoError:
        abort(503)


@identity.get("/account/closed")
def account_closed():
    if not session.get("closure_reference"):
        return redirect(url_for("index"))
    return render_template(
        "auth/account_closed.html",
        title="Your account is closed",
        context="public",
        reference=session["closure_reference"],
        review=session.get("closure_state") == "review_required",
    )


@identity.get("/privacy")
def privacy_notice():
    return render_template(
        "auth/privacy.html",
        title="Privacy and service information",
        context=session.get("context", "public"),
    )


@identity.get("/support")
def support_directory():
    return render_template(
        "support.html", title="Support services", context=session.get("context", "public")
    )
