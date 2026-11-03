"""Minimal metadata-only access administration; authoritative checks are services."""

from flask import Blueprint, current_app, g, redirect, render_template, request, session, url_for
from pymongo.errors import PyMongoError

from app.auth.routes import authenticated
from app.repositories.core import InvalidInput
from app.services.access import AccessService
from app.services.policy import AccessDenied, Policy
from app.services.transactions import VersionConflict

access = Blueprint("access", __name__)
FIELDS = {"csrf_token", "operation", "target", "team", "role", "reason", "grant_id"}


@access.route("/access", methods=["GET", "POST"])
@authenticated
def manage():
    database = current_app.extensions["mongo"][current_app.config["MONGODB_DATABASE"]]
    try:
        policy = Policy(database, g.user["_id"], session.get("context"))
        admin = policy.allows("manage_accounts")
        approver = policy.allows("approve_grant")
        if not (admin or approver):
            raise AccessDenied("Access denied.")
        if request.method == "POST":
            if set(request.form) - FIELDS or any(
                len(request.form.getlist(key)) != 1 for key in request.form
            ):
                raise InvalidInput("Invalid form.")
            data = request.form
            operation = data.get("operation")
            service = AccessService(database)
            actor = g.user["_id"]
            context = session.get("context")
            target = data.get("target")
            team = data.get("team") or None
            if operation == "request":
                service.request_grant(
                    actor, context, target, data.get("role"), team, data.get("reason")
                )
            elif operation == "approve":
                service.approve(actor, context, data.get("grant_id"), data.get("reason"))
            elif operation in {"grant_membership", "revoke_membership"}:
                service.membership(
                    actor,
                    context,
                    target,
                    team,
                    data.get("role"),
                    operation == "grant_membership",
                    data.get("reason"),
                )
            elif operation == "revoke_privilege":
                service.revoke(actor, context, target, data.get("role"), team, data.get("reason"))
            elif operation == "disable":
                service.deactivate(actor, context, target, data.get("reason"))
            else:
                raise InvalidInput("Invalid operation.")
            return redirect(url_for("access.manage"))
        users = list(
            database.users.find({}, {"display_name": 1, "account_status": 1}, max_time_ms=1500)
            .sort("display_name", 1)
            .limit(100)
        )
        teams = list(database.teams.find({"active": True}, {"name": 1}).sort("name", 1).limit(100))
        pending = list(
            database.privileged_grants.find(
                {"state": "pending"},
                {"user_id": 1, "role": 1, "team_id": 1, "requested_by": 1, "reason": 1},
            )
            .sort("created_at", 1)
            .limit(100)
        )
        return render_template(
            "auth/access.html",
            title="Manage service access",
            context="admin",
            users=users,
            teams=teams,
            pending=pending,
            admin=admin,
            approver=approver,
        )
    except AccessDenied:
        return "Access denied.", 403
    except (InvalidInput, TypeError, ValueError):
        return "Invalid request.", 400
    except PyMongoError:
        current_app.logger.error("access_operation_unavailable")
        return "Access service unavailable. No change has been confirmed.", 503


@access.route("/retention", methods=["GET", "POST"])
@authenticated
def retention():
    from app.services.lifecycle import Lifecycle

    db = current_app.extensions["mongo"][current_app.config["MONGODB_DATABASE"]]
    try:
        service = Lifecycle(db)
        if request.method == "POST":
            if set(request.form) - {"csrf_token", "operation", "case", "record", "reason"} or any(
                len(request.form.getlist(k)) != 1 for k in request.form
            ):
                raise InvalidInput("Invalid form.")
            data = request.form
            actor = g.user["_id"]
            context = session.get("context")
            if data.get("operation") == "request":
                service.request(
                    actor, context, data.get("case"), service.policy_reference, data.get("reason")
                )
            elif data.get("operation") == "approve":
                service.approve(actor, context, data.get("record"))
            elif data.get("operation") in {"hold", "release_hold"}:
                service.hold(
                    actor,
                    context,
                    data.get("case"),
                    data.get("operation") == "hold",
                    data.get("reason"),
                )
            else:
                raise InvalidInput("Invalid action.")
            return redirect(url_for("access.retention"), code=303)
        rows, ledger = service.review(g.user["_id"], session.get("context"))
        return render_template(
            "auth/retention.html",
            title="Synthetic retention review",
            context="admin",
            rows=rows,
            ledger=ledger,
            policy_reference=service.policy_reference,
            synthetic_policy=service.policy_reference == "synthetic-demo-1day",
        )
    except AccessDenied:
        return "Access denied.", 403
    except (InvalidInput, ValueError, TypeError):
        return "Invalid retention action.", 400
    except PyMongoError:
        return "Retention action not confirmed. Review before retrying.", 503


@access.route("/access/invitations", methods=["GET", "POST"])
@authenticated
def invitations():
    from app.services.enrolment import Enrolment

    if not current_app.config["REGISTRATION_AVAILABLE"]:
        return "University invitation enrolment is not enabled.", 404
    db = current_app.extensions["mongo"][current_app.config["MONGODB_DATABASE"]]
    service = Enrolment(db)
    code = None
    error = None
    status = 200
    try:
        Policy(db, g.user["_id"], session.get("context")).require("manage_accounts")
        if request.method == "POST":
            allowed = {"csrf_token", "operation", "email", "role", "team", "invitation"}
            if set(request.form) - allowed or any(
                len(request.form.getlist(k)) != 1 for k in request.form
            ):
                return "Invalid form.", 400
            try:
                if request.form.get("operation") == "create":
                    _, code = service.create(
                        g.user["_id"],
                        session.get("context"),
                        current_app.config["OIDC_ISSUER"],
                        request.form.get("email"),
                        request.form.get("role"),
                        request.form.get("team") or None,
                    )
                elif request.form.get("operation") == "revoke":
                    service.revoke(
                        g.user["_id"], session.get("context"), request.form.get("invitation")
                    )
                    return redirect(url_for("access.invitations"), code=303)
                else:
                    raise ValueError("Choose a valid action.")
            except ValueError as problem:
                error, status = str(problem), 400
        return render_template(
            "auth/invitations.html",
            title="University invitations",
            context="admin",
            rows=service.list(g.user["_id"], session.get("context")),
            teams=list(db.teams.find({"active": True}, {"name": 1}).limit(100)),
            code=code,
            error=error,
        ), status
    except AccessDenied:
        return "Access denied.", 403
    except PyMongoError:
        return "Invitation service unavailable. No change confirmed.", 503


@access.route("/access/privacy", methods=["GET", "POST"])
@authenticated
def privacy_requests():
    from app.services.account_privacy import AccountPrivacy

    db = current_app.extensions["mongo"][current_app.config["MONGODB_DATABASE"]]
    service = AccountPrivacy(db, current_app.config["IDENTITY_FINGERPRINT_KEY"])
    try:
        Policy(db, g.user["_id"], session.get("context")).require("manage_accounts")
        if request.method == "POST":
            if set(request.form) != {"csrf_token", "request", "reason", "policy", "days"} or any(
                len(request.form.getlist(k)) != 1 for k in request.form
            ):
                return "Invalid form.", 400
            service.record_retention(
                g.user["_id"],
                session.get("context"),
                request.form["request"],
                request.form["reason"],
                request.form["policy"],
                int(request.form["days"]),
            )
            return redirect(url_for("access.privacy_requests"), code=303)
        return render_template(
            "auth/privacy_requests.html",
            title="Account privacy requests",
            context="admin",
            rows=service.review(g.user["_id"], session.get("context")),
        )
    except AccessDenied:
        return "Access denied.", 403
    except (ValueError, TypeError):
        return "Enter a valid policy reference, reason and review interval.", 400
    except PyMongoError:
        return "Privacy service unavailable. No change confirmed.", 503


@access.route("/access/teams", methods=["GET", "POST"])
@authenticated
def teams():
    from app.repositories.schema import CATEGORIES
    from app.services.teams import Teams

    db = current_app.extensions["mongo"][current_app.config["MONGODB_DATABASE"]]
    service = Teams(db)
    error = None
    status = 200
    try:
        Policy(db, g.user["_id"], session.get("context")).require("manage_accounts")
        if request.method == "POST":
            allowed = {"csrf_token", "team", "version", "name", "categories", "routing", "active"}
            if set(request.form) - allowed or any(
                len(request.form.getlist(k)) != 1
                for k in request.form
                if k not in {"categories", "routing"}
            ):
                return "Invalid form.", 400
            try:
                service.save(
                    g.user["_id"],
                    session.get("context"),
                    request.form.get("name"),
                    request.form.getlist("categories"),
                    request.form.getlist("routing"),
                    team=request.form.get("team") or None,
                    version=int(request.form["version"]) if request.form.get("team") else None,
                    active=request.form.get("active") == "1",
                )
                return redirect(url_for("access.teams"), code=303)
            except VersionConflict:
                error, status = "The team changed. Review the current values before retrying.", 409
            except ValueError as problem:
                error, status = str(problem), 400
        rows = service.list(g.user["_id"], session.get("context"))
        routed = {c for team in rows if team["active"] for c in team.get("routing_categories", [])}
        return render_template(
            "auth/teams.html",
            title="Support teams and routing",
            context="admin",
            rows=rows,
            categories=CATEGORIES,
            missing=set(CATEGORIES) - routed,
            error=error,
        ), status
    except AccessDenied:
        return "Access denied.", 403
    except PyMongoError:
        return "Team configuration unavailable. No change confirmed.", 503
