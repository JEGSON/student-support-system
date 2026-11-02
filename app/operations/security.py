"""Explicit single-hop proxy boundary and shared fixed-window request budgets."""

import hashlib
import ipaddress
import time
from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from flask import abort, current_app, g, request
from pymongo import ReturnDocument
from pymongo.errors import PyMongoError

from app.repositories.core import utc_now


class TrustedProxy:
    def __init__(self, application, config):
        self.app = application
        self.config = config

    def __call__(self, environ, start_response):
        keys = [k for k in environ if k.startswith("HTTP_X_FORWARDED_") or k == "HTTP_FORWARDED"]
        trusted = self.config["TRUST_PROXY"]
        invalid = False
        if keys:
            invalid = (
                not trusted
                or environ.get("REMOTE_ADDR") != self.config["PROXY_TRUSTED_IP"]
                or set(keys) != {"HTTP_X_FORWARDED_FOR", "HTTP_X_FORWARDED_PROTO"}
            )
            try:
                client = environ.get("HTTP_X_FORWARDED_FOR", "")
                ipaddress.ip_address(client)
                invalid = invalid or environ.get("HTTP_X_FORWARDED_PROTO") != "https"
            except ValueError:
                invalid = True
            if not invalid:
                environ["REMOTE_ADDR"] = client
                environ["wsgi.url_scheme"] = "https"
        elif trusted:
            invalid = True
        if self.config["APP_ENV"] == "production" and environ.get("wsgi.url_scheme") != "https":
            invalid = True
        environ["support.proxy_invalid"] = invalid
        return self.app(environ, start_response)


def enforce_rate_limit():
    if not current_app.config["RATE_LIMIT_ENABLED"]:
        return
    endpoint = request.endpoint or ""
    if not endpoint:
        return
    if endpoint == "static" or endpoint.startswith("health.") or endpoint == "index":
        return
    group = "write" if request.method not in {"GET", "HEAD", "OPTIONS"} else "read"
    if endpoint.startswith("identity."):
        group = "identity"
    maximum = current_app.config["RATE_LIMIT_" + group.upper()]
    subject = g.user["_id"] if g.user else (request.remote_addr or "unknown")
    minute = int(time.time()) // 60
    fingerprint = hashlib.sha256(
        (current_app.secret_key + subject + group + str(minute)).encode()
    ).hexdigest()
    now = utc_now()
    key = str(uuid5(NAMESPACE_URL, "student-support/rate/" + fingerprint))
    try:
        db = current_app.extensions["mongo"][current_app.config["MONGODB_DATABASE"]]
        result = db.rate_limits.find_one_and_update(
            {"_id": key},
            {"$inc": {"count": 1}, "$setOnInsert": {"expires_at": now + timedelta(minutes=2)}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        if result["count"] > maximum:
            abort(429)
    except PyMongoError:
        current_app.logger.warning("rate_limit_storage_unavailable")
        abort(503)
