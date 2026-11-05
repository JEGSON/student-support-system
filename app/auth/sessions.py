"""Opaque, hashed MongoDB sessions. OAuth/CSRF values never enter cookies."""

import hashlib
import re
import secrets
from datetime import timedelta
from uuid import uuid4

from flask import g
from flask.sessions import SessionInterface, SessionMixin
from werkzeug.datastructures import CallbackDict

from app.auth.workspaces import cookie_settings, workspace
from app.repositories.core import utc_now

COOKIE = "support_session"
TOKEN = re.compile(r"^[A-Za-z0-9_-]{43}$")


def token_hash(token):
    return hashlib.sha256(token.encode("ascii")).hexdigest()


class ServerSession(CallbackDict, SessionMixin):
    def __init__(self, data=None, record=None, collection=None):
        super().__init__(data or {}, lambda obj: setattr(obj, "modified", True))
        self.record = record
        self.collection = collection
        self.token = None
        self.user_id = record.get("user_id") if record else None
        self.new = record is None
        self.modified = False
        self.storage_failed = False
        self.invalid_cookie = False
        self.retired = []
        self.authentication_time = record.get("authentication_time") if record else None
        self.absolute_deadline = (
            record.get("absolute_expires_at") if record and self.user_id else None
        )

    def __setitem__(self, key, value):
        if key not in {
            "csrf_token",
            "context",
            "workspace",
            "login_hint",
            "reauth_user",
            "reauth_started",
            "reauthenticated_at",
            "invitation_hash",
            "closure_reference",
            "closure_state",
        } and not key.startswith("_state_university_"):
            raise ValueError("Unsupported server-session field.")
        super().__setitem__(key, value)

    def rotate(self, user_id=None, authentication_time=None, preserve_absolute=False):
        deadline = self.absolute_deadline if preserve_absolute else None
        if self.record:
            self.retired.append((self.collection, self.record["_id"]))
        self.clear()
        self.record = None
        self.collection = None
        self.token = None
        self.user_id = user_id
        self.authentication_time = authentication_time
        self.absolute_deadline = deadline
        self.new = True
        self.modified = True

    def logout(self):
        self.rotate()
        self.invalid_cookie = True
        self.modified = False


class MongoSessionInterface(SessionInterface):
    session_class = ServerSession

    def open_session(self, app, request):
        g.user = None
        raw = request.cookies.get(cookie_settings()[0])
        result = ServerSession()
        if not raw:
            return result
        if not TOKEN.fullmatch(raw):
            result.invalid_cookie = True
            return result
        database = app.extensions["mongo"][app.config["MONGODB_DATABASE"]]
        now = utc_now()
        try:
            record = None
            collection = None
            for name in ("sessions", "auth_attempts"):
                record = database[name].find_one({"token_hash": token_hash(raw)})
                if record:
                    collection = name
                    break
            valid = (
                record
                and not record.get("revoked_at")
                and record["absolute_expires_at"] > now
                and record["idle_expires_at"] > now
                and record.get("data", {}).get("workspace", "general") == workspace()
            )
            if not valid:
                result.invalid_cookie = True
                return result
            if collection == "sessions":
                user = database.users.find_one(
                    {"_id": record["user_id"], "account_status": "active"}
                )
                if not user:
                    database.sessions.update_one(
                        {"_id": record["_id"]}, {"$set": {"revoked_at": now}}
                    )
                    result.invalid_cookie = True
                    return result
                g.user = user
            result = ServerSession(record.get("data", {}), record, collection)
            result.token = raw
            return result
        except Exception:
            result.storage_failed = True
            return result

    def save_session(self, app, session, response):
        database = app.extensions["mongo"][app.config["MONGODB_DATABASE"]]
        now = utc_now()
        response.vary.add("Cookie")
        cookie, cookie_path = cookie_settings()
        try:
            for name, key in session.retired:
                database[name].update_one({"_id": key}, {"$set": {"revoked_at": now}})
            if session.invalid_cookie:
                response.delete_cookie(
                    cookie,
                    path=cookie_path,
                    secure=app.config["SESSION_COOKIE_SECURE"],
                    httponly=True,
                    samesite="Lax",
                )
            if session.storage_failed or (not session.modified and not session.record):
                return
            collection = "sessions" if session.user_id else "auth_attempts"
            absolute = session.absolute_deadline or (
                session.record["absolute_expires_at"]
                if session.record
                else now + (timedelta(hours=8) if session.user_id else timedelta(minutes=10))
            )
            idle_minutes = 30 if session.get("context") == "student" else 20
            idle = min(absolute, now + timedelta(minutes=idle_minutes if session.user_id else 10))
            if session.new:
                session.token = secrets.token_urlsafe(32)
                record = {
                    "_id": str(uuid4()),
                    "token_hash": token_hash(session.token),
                    "data": {**dict(session), "workspace": workspace()},
                    "created_at": now,
                    "last_seen_at": now,
                    "idle_expires_at": idle,
                    "absolute_expires_at": absolute,
                    "version": 0,
                }
                if app.config["TESTING"]:
                    record["fixture_version"] = "synthetic-v1"
                if session.user_id:
                    record.update(
                        user_id=session.user_id,
                        authentication_time=session.authentication_time or now,
                    )
                database[collection].insert_one(record)
            else:
                query = {
                    "_id": session.record["_id"],
                    "revoked_at": None,
                    "absolute_expires_at": {"$gt": now},
                    "idle_expires_at": {"$gt": now},
                }
                update = {"$max": {"last_seen_at": now, "idle_expires_at": idle}}
                if session.modified:
                    query["version"] = session.record.get("version", 0)
                    update.update({"$set": {"data": dict(session)}, "$inc": {"version": 1}})
                if not database[collection].update_one(query, update).matched_count:
                    response.delete_cookie(
                        cookie,
                        path=cookie_path,
                        secure=app.config["SESSION_COOKIE_SECURE"],
                        httponly=True,
                        samesite="Lax",
                    )
                    return
            response.set_cookie(
                cookie,
                session.token,
                max_age=max(1, int((absolute - now).total_seconds())),
                secure=app.config["SESSION_COOKIE_SECURE"],
                httponly=True,
                samesite="Lax",
                path=cookie_path,
            )
        except Exception:
            app.logger.error("session_storage_unavailable")
            response.status_code = 503
            response.set_data("Service unavailable. Please try again.")
            response.headers["Cache-Control"] = "no-store"
