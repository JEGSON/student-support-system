"""Explicit environment contract; no development defaults in production."""

import ipaddress
import json
import os
import re
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID


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
        "OIDC_CLIENT_ID",
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
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,62}", database) or database in {
        "admin",
        "local",
        "config",
    }:
        raise ConfigurationError("Invalid database name.")
    if not local and (
        database in expected.values() or database.startswith("student_support_restore_")
    ):
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
    method = source.get("OIDC_TOKEN_AUTH_METHOD", "none" if local else "client_secret_basic")
    if method not in {"none", "client_secret_basic"}:
        raise ConfigurationError("Unsupported identity client authentication method.")
    if method != "none" and not source.get("OIDC_CLIENT_SECRET"):
        raise ConfigurationError("A confidential identity client requires its secret.")
    if not local and not source.get("OIDC_REQUIRED_ACR"):
        raise ConfigurationError(
            "Production requires an institution-approved authentication class."
        )

    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate routing key.")
            result[key] = value
        return result

    try:
        routing = json.loads(source.get("CASE_ROUTING_JSON", "{}"), object_pairs_hook=unique_pairs)
        if not isinstance(routing, dict):
            raise ValueError
        for category, team in routing.items():
            if (
                category not in {"academic", "finance", "wellbeing", "disability", "accommodation"}
                or not isinstance(team, str)
                or str(UUID(team)) != team
            ):
                raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise ConfigurationError(
            "CASE_ROUTING_JSON must map approved categories to canonical team UUIDs."
        ) from None
    trust_proxy = str(source.get("TRUST_PROXY", "0"))
    if trust_proxy not in {"0", "1"}:
        raise ConfigurationError("TRUST_PROXY must be 0 or 1.")
    trusted_ip = source.get("PROXY_TRUSTED_IP", "127.0.0.1")
    if trust_proxy == "1":
        if str(source.get("PROXY_HOPS", "")) != "1":
            raise ConfigurationError("Exactly one trusted proxy hop is required.")
        try:
            ipaddress.ip_address(trusted_ip)
        except ValueError:
            raise ConfigurationError("Invalid trusted proxy address.") from None
    enabled = str(source.get("RATE_LIMIT_ENABLED", "1" if not local else "0"))
    if enabled not in {"0", "1"} or (not local and enabled != "1"):
        raise ConfigurationError("Production requires shared rate limiting.")
    rates = {}
    for name, default in [("READ", 600), ("WRITE", 120), ("IDENTITY", 30)]:
        try:
            value = int(str(source.get("RATE_LIMIT_" + name, default)))
        except ValueError:
            raise ConfigurationError("Invalid rate limit.") from None
        if not 1 <= value <= 10000:
            raise ConfigurationError("Rate limit must be 1–10000.")
        rates["RATE_LIMIT_" + name] = value
    registration = str(source.get("SELF_REGISTRATION_ENABLED", "0"))
    if registration not in {"0", "1"}:
        raise ConfigurationError("SELF_REGISTRATION_ENABLED must be 0 or 1.")
    if registration == "1" and (
        not local or source["OIDC_ISSUER"] != "http://127.0.0.1:8180/realms/student-support"
    ):
        raise ConfigurationError("Self-registration is restricted to the local synthetic provider.")
    enrolment = source.get(
        "ENROLMENT_MODE", "local_demo" if registration == "1" else "preprovisioned"
    )
    if enrolment not in {"local_demo", "preprovisioned", "invitation"} or (
        not local and enrolment == "local_demo"
    ):
        raise ConfigurationError("Choose a valid university enrolment mode.")
    identity_key = source.get("IDENTITY_FINGERPRINT_KEY", secret if local else "")
    if not isinstance(identity_key, str) or len(identity_key) < 48 or "REPLACE_" in identity_key:
        raise ConfigurationError("A stable IDENTITY_FINGERPRINT_KEY must be configured separately.")
    try:
        previous_keys = json.loads(source.get("IDENTITY_FINGERPRINT_PREVIOUS_KEYS", "[]"))
        if (
            not isinstance(previous_keys, list)
            or len(previous_keys) > 3
            or any(not isinstance(k, str) or len(k) < 48 for k in previous_keys)
            or len(set(previous_keys)) != len(previous_keys)
        ):
            raise ValueError
    except (ValueError, TypeError):
        raise ConfigurationError(
            "Configure at most three distinct previous identity-protection keys."
        ) from None
    try:
        retention_days = json.loads(
            source.get("RETENTION_DAYS_JSON", "{}"), object_pairs_hook=unique_pairs
        )
        categories = {"academic", "finance", "wellbeing", "disability", "accommodation"}
        if (
            not isinstance(retention_days, dict)
            or set(retention_days) - categories
            or any(type(v) is not int or not 1 <= v <= 36500 for v in retention_days.values())
        ):
            raise ValueError
    except (ValueError, TypeError):
        raise ConfigurationError(
            "RETENTION_DAYS_JSON must contain approved category/day values."
        ) from None
    retention_reference = source.get("RETENTION_POLICY_REFERENCE", "")
    if (
        (retention_days and not retention_reference)
        or len(retention_reference) > 200
        or (
            not local
            and (
                set(retention_days) != categories
                or not retention_reference
                or retention_reference == "synthetic-demo-1day"
            )
        )
    ):
        raise ConfigurationError(
            "Production requires an approved retention-policy reference and all five category durations."
        )
    routing_source = source.get("CASE_ROUTING_SOURCE", "environment" if local else "database")
    if routing_source not in {"environment", "database"} or (
        not local and routing_source != "database"
    ):
        raise ConfigurationError(
            "Production intake routing must use administrator-managed database routes."
        )
    try:
        privacy_review_days = int(source.get("ACCOUNT_PRIVACY_REVIEW_DAYS", "30" if local else "0"))
    except (ValueError, TypeError):
        raise ConfigurationError(
            "Configure ACCOUNT_PRIVACY_REVIEW_DAYS from the approved review procedure."
        ) from None
    if not 1 <= privacy_review_days <= 366:
        raise ConfigurationError(
            "Account privacy requests require a review interval from 1 to 366 days."
        )
    presentation = {}
    defaults = {
        "INSTITUTION_NAME": "University Student Support",
        "PRIVACY_CONTACT": "Contact your university's privacy office.",
        "PRIVACY_NOTICE": "Privacy information must be provided by the university before launch.",
        "SERVICE_HOURS_TEXT": "Service hours must be confirmed by the university.",
        "URGENT_HELP_TEXT": "Urgent-help arrangements must be confirmed by the university.",
    }
    for name, default in defaults.items():
        value = source.get(name, default if local else "")
        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value) > 12000
            or "REPLACE_" in value
        ):
            raise ConfigurationError(f"{name} must contain university-approved information.")
        presentation[name] = value.strip()
    if not local and source.get("SERVICE_POLICY_APPROVED") != "1":
        raise ConfigurationError(
            "Production requires the operator's SERVICE_POLICY_APPROVED acknowledgement."
        )
    account_url = source.get("OIDC_ACCOUNT_URL", "")
    if account_url:
        parsed = service_url(account_url, "OIDC_ACCOUNT_URL")
        issuer_origin = service_url(source["OIDC_ISSUER"], "OIDC_ISSUER")
        if (
            (parsed.scheme, parsed.netloc) != (issuer_origin.scheme, issuer_origin.netloc)
            or parsed.username
            or parsed.query
            or parsed.fragment
        ):
            raise ConfigurationError(
                "OIDC_ACCOUNT_URL must be an approved same-provider account page."
            )
    return {
        **presentation,
        "ACCOUNT_PRIVACY_REVIEW_DAYS": privacy_review_days,
        "ENROLMENT_MODE": enrolment,
        "DEMO_MODE": enrolment == "local_demo",
        "REGISTRATION_AVAILABLE": enrolment in {"local_demo", "invitation"},
        "IDENTITY_FINGERPRINT_KEY": identity_key,
        "IDENTITY_FINGERPRINT_PREVIOUS_KEYS": previous_keys,
        "RETENTION_DAYS": retention_days,
        "RETENTION_POLICY_REFERENCE": retention_reference,
        "SERVICE_POLICY_APPROVED": source.get("SERVICE_POLICY_APPROVED") == "1",
        "OIDC_ACCOUNT_URL": account_url,
        "SELF_REGISTRATION_ENABLED": registration == "1",
        "TRUST_PROXY": trust_proxy == "1",
        "PROXY_TRUSTED_IP": trusted_ip,
        "RATE_LIMIT_ENABLED": enabled == "1",
        **rates,
        "CASE_ROUTING": routing,
        "CASE_ROUTING_SOURCE": routing_source,
        "OIDC_TOKEN_AUTH_METHOD": method,
        "OIDC_CLIENT_SECRET": source.get("OIDC_CLIENT_SECRET"),
        "OIDC_REQUIRED_ACR": source.get("OIDC_REQUIRED_ACR"),
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
