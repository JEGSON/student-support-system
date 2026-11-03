"""Explicit loopback-only development runner; debugger cannot be enabled."""

import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import dotenv_values
from werkzeug.serving import WSGIRequestHandler

from app import create_app


class SafeRequestHandler(WSGIRequestHandler):
    def log_request(self, code="-", size="-"):
        self.log("info", "request method=%s status=%s", self.command, code)


def local_web_settings():
    # Keep operator/maintenance/worker credentials out of the retained web config
    # and os.environ. This local account can still read its own private .env file.
    allowed = {
        "IDENTITY_FINGERPRINT_PREVIOUS_KEYS",
        "RETENTION_DAYS_JSON",
        "RETENTION_POLICY_REFERENCE",
        "ACCOUNT_PRIVACY_REVIEW_DAYS",
        "ENROLMENT_MODE",
        "IDENTITY_FINGERPRINT_KEY",
        "INSTITUTION_NAME",
        "PRIVACY_CONTACT",
        "PRIVACY_NOTICE",
        "SERVICE_HOURS_TEXT",
        "URGENT_HELP_TEXT",
        "SERVICE_POLICY_APPROVED",
        "OIDC_ACCOUNT_URL",
        "APP_ENV",
        "SELF_REGISTRATION_ENABLED",
        "SECRET_KEY",
        "FLASK_DEBUG",
        "APP_BASE_URL",
        "MONGODB_URI",
        "MONGODB_DATABASE",
        "MONGO_MAX_POOL_SIZE",
        "OIDC_ISSUER",
        "OIDC_CLIENT_ID",
        "OIDC_CLIENT_SECRET",
        "OIDC_TOKEN_AUTH_METHOD",
        "OIDC_REQUIRED_ACR",
        "EMAIL_HEALTH_URL",
        "CASE_ROUTING_JSON",
        "CASE_ROUTING_SOURCE",
        "TRUST_PROXY",
        "PROXY_HOPS",
        "PROXY_TRUSTED_IP",
        "RATE_LIMIT_ENABLED",
        "RATE_LIMIT_READ",
        "RATE_LIMIT_WRITE",
        "RATE_LIMIT_IDENTITY",
    }
    return {
        key: value
        for key, value in dotenv_values(Path(__file__).resolve().parents[1] / ".env").items()
        if key in allowed
    }


def main():
    app = create_app(local_web_settings())
    if app.config["APP_ENV"] != "development":
        raise SystemExit("This runner is restricted to local development.")
    app.run(
        host="127.0.0.1",
        port=urlsplit(app.config["APP_BASE_URL"]).port or 5050,
        debug=False,
        use_reloader=False,
        request_handler=SafeRequestHandler,
    )


if __name__ == "__main__":
    main()
