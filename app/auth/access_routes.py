"""Minimal metadata-only access administration; authoritative checks are services."""

from flask import Blueprint, current_app, g, redirect, render_template, request, session, url_for
from pymongo.errors import PyMongoError

from app.auth.routes import authenticated
from app.repositories.core import InvalidInput
from app.services.access import AccessService
from app.services.policy import AccessDenied, Policy

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
