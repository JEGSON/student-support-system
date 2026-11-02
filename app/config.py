"""Explicit environment contract; no development defaults in production."""

import os
import re
from urllib.parse import parse_qsl, urlsplit


class ConfigurationError(ValueError):
    """Safe configuration failure without including configuration values."""


def service_url(value, key):
    try:
        url = urlsplit(value)
        # Accessing .port validates non-numeric and out-of-range ports too.
        port = url.port
    except ValueError:
        raise ConfigurationError(f"{key} must be a valid service URL.") from None
    if port == 0:
        raise ConfigurationError(f"{key} must use a valid service port.")
    return url


def load_config(overrides=None):
    source = dict(os.environ)
    source.update(overrides or {})
    env = source.get("APP_ENV")
    if env not in {"development", "testing", "production"}:
        raise ConfigurationError("APP_ENV must be explicitly configured.")
    if str(source.get("FLASK_DEBUG", "0")).lower() not in {"0", "false"}:
        raise ConfigurationError("The interactive debugger is not permitted.")
    required = [
        "SECRET_KEY",
        "MONGODB_URI",
        "MONGODB_DATABASE",
        "OIDC_ISSUER",
        "APP_BASE_URL",
        "EMAIL_HEALTH_URL",
    ]
    for key in required:
        value = source.get(key)
        if not isinstance(value, str) or not value or "REPLACE_" in value:
            raise ConfigurationError(f"{key} must be configured.")
    secret = source["SECRET_KEY"]
    if len(secret) < 48:
        raise ConfigurationError("SECRET_KEY must contain a generated secret.")
    local = env != "production"
    if not local and secret.startswith("dev-"):
        raise ConfigurationError("Development secrets are forbidden in production.")
    for key in ["APP_BASE_URL", "OIDC_ISSUER", "EMAIL_HEALTH_URL"]:
        url = service_url(source[key], key)
        if url.username or url.password or url.query or url.fragment or not url.hostname:
            raise ConfigurationError(f"{key} must be a safe service origin/path.")
        if local:
            if url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost"}:
                raise ConfigurationError("Local dependencies must use loopback HTTP.")
        elif url.scheme != "https":
            raise ConfigurationError("Production service origins must use HTTPS.")
    base = service_url(source["APP_BASE_URL"], "APP_BASE_URL")
    if base.path not in {"", "/"}:
        raise ConfigurationError("APP_BASE_URL must be an origin.")
    database = source["MONGODB_DATABASE"]
    expected = {"development": "student_support_dev", "testing": "student_support_test"}
    if local and database != expected[env]:
        raise ConfigurationError("Development and test databases must be isolated.")
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,62}", database):
        raise ConfigurationError("Invalid database name.")
    if not local and database in expected.values():
        raise ConfigurationError("Production cannot use a development/test database.")
    # Deeper URI validation is performed by PyMongo without printing the URI.
    if not source["MONGODB_URI"].startswith(("mongodb://", "mongodb+srv://")):
        raise ConfigurationError("Invalid database connection configuration.")
    if local:
        # Local tooling must not accidentally contact an institutional/production
        # database even if its database name happens to match the test convention.
        try:
            mongo = urlsplit(source["MONGODB_URI"])
            valid_local = (
                mongo.scheme == "mongodb"
                and mongo.hostname in {"localhost", "127.0.0.1"}
                and "," not in mongo.netloc
            )
        except ValueError:
            valid_local = False
        if not valid_local:
            raise ConfigurationError("Local databases must use the loopback development topology.")
    if not local:
        options = [
            (k.lower(), v.lower()) for k, v in parse_qsl(urlsplit(source["MONGODB_URI"]).query)
        ]
        if len({k for k, _ in options}) != len(options):
            raise ConfigurationError("Duplicate database options are forbidden.")
        options = dict(options)
        srv = source["MONGODB_URI"].startswith("mongodb+srv://")
        if options.get("tls", "true" if srv else "false") != "true":
            raise ConfigurationError("Production database TLS must be configured.")
        if any(
            options.get(k, "false") != "false"
            for k in ["tlsinsecure", "tlsallowinvalidcertificates", "tlsallowinvalidhostnames"]
        ):
            raise ConfigurationError("Insecure database TLS options are forbidden.")
    try:
        pool_size = int(str(source.get("MONGO_MAX_POOL_SIZE", "20")))
    except ValueError:
        raise ConfigurationError("MONGO_MAX_POOL_SIZE must be an integer from 1 to 100.") from None
    if not 1 <= pool_size <= 100:
        raise ConfigurationError("MONGO_MAX_POOL_SIZE must be an integer from 1 to 100.")
    return {
        **{key: source[key] for key in required},
        "APP_ENV": env,
        "TESTING": env == "testing",
        "DEBUG": False,
        "TRUSTED_HOSTS": ["127.0.0.1", "localhost"] if local else [base.hostname],
        "SECRET_KEY": secret,
        "MAX_CONTENT_LENGTH": 64 * 1024,
        "SESSION_COOKIE_SECURE": not local,
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SEND_FILE_MAX_AGE_DEFAULT": 0,
        "MONGO_MAX_POOL_SIZE": pool_size,
    }
