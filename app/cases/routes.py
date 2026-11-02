"""CSRF protected student HTML endpoints; no raw database documents serialized."""

import hashlib
import secrets
from datetime import datetime

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
from itsdangerous import BadData, URLSafeTimedSerializer
from pymongo.errors import PyMongoError

from app.auth.routes import authenticated
from app.repositories.core import InvalidInput, identifier, london_time
from app.repositories.schema import CATEGORIES
from app.services.policy import AccessDenied
from app.services.student_cases import (
    RoutingUnavailable,
    StudentCases,
    normalize_description,
    validate_submission,
)
from app.services.transactions import VersionConflict

cases = Blueprint("cases", __name__)


def signer(salt):
    return URLSafeTimedSerializer(current_app.secret_key, salt=salt)


def form_key():
    return signer("case-submission-v1").dumps(
        {"user": g.user["_id"], "nonce": secrets.token_urlsafe(32)}
    )


def verified_key(raw):
    if not isinstance(raw, str) or len(raw) > 1000:
        raise InvalidInput("Invalid submission key.")
    try:
        value = signer("case-submission-v1").loads(raw, max_age=24 * 60 * 60)
        if value["user"] != g.user["_id"] or len(value["nonce"]) != 43:
            raise ValueError
    except (BadData, KeyError, TypeError, ValueError):
        raise InvalidInput("Expired or invalid submission key.") from None
    return hashlib.sha256(raw.encode()).hexdigest()


def service():
    return StudentCases(
        current_app.extensions["mongo"][current_app.config["MONGODB_DATABASE"]],
        current_app.config["CASE_ROUTING"],
    )


def error_page(title, message, status):
    return render_template("error.html", title=title, message=message, context="student"), status


@cases.app_template_filter("london_time")
def display_time(value):
    return london_time(value)


@cases.before_request
def require_student_context():
    if g.user and (session.get("context") != "student" or "student" not in g.user["global_roles"]):
        abort(403)


@cases.get("/cases")
@authenticated
def overview():
    try:
        after = None
        if set(request.args) - {"after"} or len(request.args.getlist("after")) > 1:
            raise InvalidInput("Invalid page.")
        if request.args.get("after"):
            raw = request.args["after"]
            if len(raw) > 1000:
                raise InvalidInput("Invalid cursor.")
            data = signer("student-cursor-v1").loads(raw, max_age=3600)
            if data["user"] != g.user["_id"]:
                raise InvalidInput("Invalid cursor.")
            stamp = datetime.fromisoformat(data["stamp"])
            if stamp.tzinfo is None:
                raise InvalidInput("Invalid cursor.")
            after = (stamp, identifier(data["id"]))
        rows, cursor = service().list(g.user["_id"], session.get("context"), after)
        next_cursor = (
            signer("student-cursor-v1").dumps(
                {"user": g.user["_id"], "stamp": cursor[0].isoformat(), "id": cursor[1]}
            )
            if cursor
            else None
        )
        return render_template(
            "cases/overview.html",
            title="Your requests",
            context="student",
            rows=rows,
            next_cursor=next_cursor,
        )
    except (InvalidInput, BadData, ValueError, KeyError, TypeError):
        return error_page(
            "This page link has expired",
            "Open Your requests again to see the latest information.",
            400,
        )
    except AccessDenied:
        abort(403)
    except PyMongoError:
        return error_page(
            "Requests are temporarily unavailable",
            "Please try again. Your requests have not been changed.",
            503,
        )


@cases.route("/cases/new", methods=["GET", "POST"])
@authenticated
def new_request():
    errors = {}
    category = ""
    description = ""
    key = form_key()
    status = 200
    if request.method == "POST":
        if (
            request.mimetype != "application/x-www-form-urlencoded"
            or set(request.form) - {"csrf_token", "submission_key", "category", "description"}
            or any(len(request.form.getlist(k)) != 1 for k in request.form)
        ):
            return error_page(
                "We could not accept this form", "Open a new request form and try again.", 400
            )
        category = request.form.get("category", "")
        description = normalize_description(request.form.get("description", ""))
        key = request.form.get("submission_key", "")
        try:
            key_hash = verified_key(key)
            errors = validate_submission(category, description)
            if not errors:
                case_id = service().create(
                    g.user["_id"], session.get("context"), category, description, key_hash
                )
                return redirect(url_for("cases.detail", case_id=case_id, submitted="1"), code=303)
            status = 422
        except InvalidInput:
            return error_page(
                "Your request form has expired",
                "Open a new form and submit it again. This attempt made no change.",
                400,
            )
        except VersionConflict:
            return error_page(
                "This form has already been used",
                "Open Your requests to check the recorded request. Use a new form for a different request.",
                409,
            )
        except AccessDenied:
            abort(403)
        except (RoutingUnavailable, PyMongoError):
            errors["service"] = (
                "We could not confirm your submission. Retry this same form to avoid a duplicate. You can also check Your requests."
            )
            status = 503
    return render_template(
        "cases/new.html",
        title="New support request",
        context="student",
        categories=CATEGORIES,
        category=category,
        description=description,
        submission_key=key,
        errors=errors,
    ), status


@cases.get("/cases/<case_id>")
@authenticated
def detail(case_id):
    try:
        case = service().detail(g.user["_id"], session.get("context"), case_id)
        from app.cases.thread_helpers import cursor, encode_cursor
        from app.services.communication import Communication

        thread, older, version = Communication(
            current_app.extensions["mongo"][current_app.config["MONGODB_DATABASE"]]
        ).thread(g.user["_id"], session.get("context"), case_id, before=cursor(case_id, "messages"))
        case["version"] = version
        return render_template(
            "cases/detail.html",
            messages=thread,
            older=encode_cursor(case_id, "messages", older),
            submission_key=form_key(),
            title="Your support request",
            context="student",
            case=case,
            submitted=request.args.get("submitted") == "1",
        )
    except (AccessDenied, InvalidInput):
        abort(404)
    except (BadData, KeyError, TypeError, ValueError):
        abort(400)
    except PyMongoError:
        return error_page(
            "Your request is temporarily unavailable",
            "Please try again. No change has been made.",
            503,
        )


@cases.post("/cases/<case_id>/message")
@authenticated
def message(case_id):
    from app.services.communication import Communication

    try:
        if set(request.form) - {
            "csrf_token",
            "submission_key",
            "version",
            "body",
            "correction",
        } or any(len(request.form.getlist(k)) != 1 for k in request.form):
            raise InvalidInput("Invalid form.")
        Communication(current_app.extensions["mongo"][current_app.config["MONGODB_DATABASE"]]).act(
            g.user["_id"],
            session.get("context"),
            case_id,
            int(request.form.get("version", "0")),
            "message",
            body=request.form.get("body"),
            correction=request.form.get("correction") or None,
            key_hash=verified_key(request.form.get("submission_key")),
        )
        return redirect(url_for("cases.detail", case_id=case_id), code=303)
    except AccessDenied:
        abort(404)
    except VersionConflict:
        return error_page(
            "This request has changed",
            "Review the latest conversation and retry with the same text.",
            409,
        )
    except (ValueError, TypeError):
        return error_page(
            "Check your message", "Use plain text up to 10,000 characters and a current form.", 400
        )
    except PyMongoError:
        return error_page(
            "Message not confirmed", "Check the conversation before retrying the same form.", 503
        )
