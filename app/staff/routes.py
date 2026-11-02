"""Staff entry points; service policy remains authoritative."""

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
from itsdangerous import BadData
from pymongo.errors import PyMongoError

from app.auth.routes import authenticated
from app.services.access import AccessService
from app.services.policy import AccessDenied
from app.services.staff_cases import StaffCases
from app.services.transactions import VersionConflict

staff = Blueprint("staff", __name__)


def database():
    return current_app.extensions["mongo"][current_app.config["MONGODB_DATABASE"]]


def form_fields(allowed):
    if (
        request.mimetype != "application/x-www-form-urlencoded"
        or set(request.form) - ({"csrf_token"} | set(allowed))
        or any(len(request.form.getlist(k)) != 1 for k in request.form)
    ):
        raise ValueError("Invalid form.")
    return request.form


@staff.before_request
def context():
    if g.user and session.get("context") != "staff":
        abort(403)


@staff.errorhandler(AccessDenied)
def denied(error):
    return render_template(
        "error.html",
        title="Request unavailable",
        message="You do not have access to this request.",
        context="staff",
    ), 404


@staff.errorhandler(BadData)
@staff.errorhandler(KeyError)
@staff.errorhandler(TypeError)
@staff.errorhandler(ValueError)
def invalid(error):
    return render_template(
        "error.html",
        title="Check your action",
        message="The submitted action is invalid. Review the request and try again.",
        context="staff",
    ), 400


@staff.errorhandler(VersionConflict)
def conflict(error):
    return render_template(
        "error.html",
        title="This request has changed",
        message="Open the request again and review the latest information before retrying.",
        context="staff",
    ), 409


@staff.errorhandler(PyMongoError)
def unavailable(error):
    return render_template(
        "error.html",
        title="Service temporarily unavailable",
        message="No change has been confirmed. Check the request before retrying.",
        context="staff",
    ), 503


@staff.get("/staff")
@authenticated
def queue():
    if set(request.args) - {"status", "after"}:
        raise ValueError("Invalid filter.")
    rows, more = StaffCases(database()).queue(
        g.user["_id"], session.get("context"), request.args.get("status"), request.args.get("after")
    )
    return render_template(
        "staff/queue.html",
        title="Staff workspace",
        context="staff",
        rows=rows,
        more=more,
        status=request.args.get("status", ""),
    )


@staff.get("/staff/cases/<case_id>")
@authenticated
def detail(case_id):
    case = StaffCases(database()).read(g.user["_id"], session.get("context"), case_id)
    from app.cases.thread_helpers import cursor, encode_cursor
    from app.services.communication import Communication

    comm = Communication(database())
    messages, more, _ = comm.thread(
        g.user["_id"], session.get("context"), case_id, before=cursor(case_id, "messages")
    )
    notes, nmore, version = comm.thread(
        g.user["_id"], session.get("context"), case_id, notes=True, before=cursor(case_id, "notes")
    )
    case["version"] = version
    return render_template(
        "staff/detail.html",
        title="Case workspace",
        context="staff",
        case=case,
        messages=messages,
        notes=notes,
        older=encode_cursor(case_id, "messages", more),
        older_notes=encode_cursor(case_id, "notes", nmore),
    )


@staff.post("/staff/cases/<case_id>/action")
@authenticated
def action(case_id):
    data = form_fields({"operation", "version", "assignee", "team", "reason"})
    StaffCases(database()).mutate(
        g.user["_id"],
        session.get("context"),
        case_id,
        int(data.get("version", "0")),
        data.get("operation"),
        assignee=data.get("assignee"),
        team=data.get("team"),
        reason=data.get("reason"),
    )
    return redirect(url_for("staff.queue"), code=303)


@staff.post("/staff/cases/<case_id>/claim")
@authenticated
def claim(case_id):
    form_fields(set())
    AccessService(database()).claim(g.user["_id"], session.get("context"), case_id)
    return redirect(url_for("staff.triage", case_id=case_id), code=303)


@staff.get("/staff/triage/<case_id>")
@authenticated
def triage(case_id):
    case = StaffCases(database()).read(g.user["_id"], session.get("context"), case_id, triage=True)
    teams = list(
        database()
        .teams.find({"active": True, "category_scope": case["category"]}, {"name": 1})
        .limit(100)
    )
    return render_template(
        "staff/triage.html",
        title="Initial request routing",
        context="staff",
        case=case,
        teams=teams,
    )


@staff.post("/staff/triage/<case_id>/release")
@authenticated
def release(case_id):
    form_fields(set())
    StaffCases(database()).release(g.user["_id"], session.get("context"), case_id)
    return redirect(url_for("staff.queue"), code=303)


@staff.post("/staff/cases/<case_id>/communicate")
@authenticated
def communicate(case_id):
    from app.services.communication import Communication

    data = form_fields({"operation", "version", "body", "reason", "correction", "assignee"})
    Communication(database()).act(
        g.user["_id"],
        session.get("context"),
        case_id,
        int(data.get("version", "0")),
        data.get("operation"),
        body=data.get("body", ""),
        reason=data.get("reason", ""),
        correction=data.get("correction") or None,
        assignee=data.get("assignee") or None,
    )
    return redirect(url_for("staff.detail", case_id=case_id), code=303)
