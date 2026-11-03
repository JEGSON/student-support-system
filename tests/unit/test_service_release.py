import ssl
from uuid import uuid4

import pytest
from test_runtime import production_config

from app.config import ConfigurationError, load_config
from app.services.accounts import LOCAL_ISSUER, Accounts
from app.services.enrolment import contact_address, invitation_hash
from app.services.policy import AccessDenied
from worker.delivery import SMTPDelivery


@pytest.mark.parametrize(
    "address",
    [
        "a\r\nBcc: victim@university.ac.uk",
        "a@localhost",
        "a..b@example.org",
        " name@example.org",
        "a@-invalid.org",
        {},
        "a@b@c.org",
    ],
)
def test_contact_rejects_header_injection_and_invalid_addresses(address):
    with pytest.raises(ValueError):
        contact_address(address)


def test_verified_email_normalisation_and_opaque_invite_code():
    assert contact_address("O'Brien@University.AC.UK") == "o'brien@university.ac.uk"
    with pytest.raises(ValueError):
        invitation_hash("short")


def test_real_enrolment_and_policy_are_explicit(config):
    values = production_config(config)
    settings = load_config({**values, "ENROLMENT_MODE": "invitation"})
    assert settings["REGISTRATION_AVAILABLE"] and not settings["DEMO_MODE"]
    assert settings["CASE_ROUTING_SOURCE"] == "database"
    with pytest.raises(AccessDenied):
        Accounts(None).resolve(LOCAL_ISSUER, {"sub": "test-subject"}, allow_registration=True)
    for invalid in [
        {"IDENTITY_FINGERPRINT_KEY": ""},
        {"RETENTION_DAYS_JSON": "{}"},
        {"SERVICE_POLICY_APPROVED": "0"},
        {"ENROLMENT_MODE": "local_demo"},
        {"CASE_ROUTING_SOURCE": "environment"},
        {"PRIVACY_NOTICE": ""},
        {"OIDC_ACCOUNT_URL": "https://attacker.invalid/redirect"},
        {"IDENTITY_FINGERPRINT_PREVIOUS_KEYS": '["short"]'},
    ]:
        with pytest.raises(ConfigurationError):
            load_config({**values, **invalid})


def smtp_settings():
    return {
        "APP_ENV": "production",
        "EMAIL_DELIVERY_ENABLED": "1",
        "APP_BASE_URL": "https://support.university.ac.uk",
        "SMTP_HOST": "smtp.university.ac.uk",
        "SMTP_PORT": "587",
        "SMTP_SECURITY": "starttls",
        "SMTP_USERNAME": "service-test",
        "SMTP_PASSWORD": "unit-test-password",
        "SMTP_FROM": "support@university.ac.uk",
    }


def test_smtp_requires_optin_and_rejects_plaintext_or_capture_contact():
    for change in [
        {"EMAIL_DELIVERY_ENABLED": "0"},
        {"APP_ENV": "development"},
        {"SMTP_SECURITY": "none"},
        {"APP_BASE_URL": "http://support.university.ac.uk"},
        {"SMTP_FROM": "sender@example.invalid"},
    ]:
        with pytest.raises(ValueError):
            SMTPDelivery(None, str(uuid4()), {**smtp_settings(), **change})
    delivery = SMTPDelivery(None, str(uuid4()), smtp_settings())
    job = {
        "event_key": "event",
        "recipient_user_id": str(uuid4()),
        "channel": "email",
        "template_key": "case_updated",
        "description": "PRIVATE_NARRATIVE",
        "note": "PRIVATE_NOTE",
    }
    msg = delivery.message(job, "student@university.ac.uk")
    assert "PRIVATE_" not in msg.as_string() and "/cases" in msg.get_content()
    with pytest.raises(ValueError):
        delivery.message(job, "someone@example.invalid")


@pytest.mark.parametrize("security", ["ssl", "starttls"])
def test_smtp_verifies_tls_before_authentication(monkeypatch, security):
    calls = []

    class Connection:
        def __init__(self, *args, **kwargs):
            calls.append(("connect", kwargs.get("context")))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def ehlo(self):
            calls.append(("ehlo", None))

        def starttls(self, context):
            calls.append(("tls", context))

        def login(self, *args):
            calls.append(("login", None))

        def send_message(self, msg):
            calls.append(("send", None))

    monkeypatch.setattr("worker.delivery.smtplib.SMTP_SSL", Connection)
    monkeypatch.setattr("worker.delivery.smtplib.SMTP", Connection)
    delivery = SMTPDelivery(None, str(uuid4()), {**smtp_settings(), "SMTP_SECURITY": security})
    delivery.send(object())
    context = next(value for name, value in calls if value is not None)
    assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    assert [name for name, _ in calls].index("login") < [name for name, _ in calls].index("send")
    if security == "starttls":
        assert [name for name, _ in calls].index("tls") < [name for name, _ in calls].index("login")
