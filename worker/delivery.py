"""Generic notification delivery through local capture or opt-in authenticated TLS."""

import hashlib
import re
import smtplib
from datetime import timedelta
from email.message import EmailMessage
from email.utils import format_datetime
from urllib.parse import urlsplit

from app.repositories.core import utc_now
from app.services.outbox import TEMPLATES, NotificationJobs


class LocalDelivery:
    def __init__(self, database, principal, app_origin):
        origin = urlsplit(app_origin)
        if (
            origin.scheme != "http"
            or origin.hostname not in {"127.0.0.1", "localhost"}
            or origin.path not in {"", "/"}
            or origin.query
            or origin.fragment
            or origin.username
        ):
            raise ValueError("Only loopback synthetic delivery is enabled.")
        self.db = database
        self.jobs = NotificationJobs(database, principal)
        self.origin = app_origin.rstrip("/")

    def message(self, job, contact):
        if job["template_key"] not in TEMPLATES or not re.fullmatch(
            r"[A-Za-z0-9_.+-]+@example\.invalid", contact
        ):
            raise ValueError("Synthetic verified contact required.")
        msg = EmailMessage()
        msg["From"] = "Student Support demo <support-demo@example.invalid>"
        msg["To"] = contact
        msg["Subject"] = "An update in Student Support"
        msg["Date"] = format_datetime(utc_now())
        event = hashlib.sha256(
            (job["event_key"] + job["recipient_user_id"] + job["channel"]).encode()
        ).hexdigest()
        msg["Message-ID"] = "<" + event + "@student-support.example.invalid>"
        msg.set_content(
            "There is an update in your Student Support account.\nSign in to view your requests:\n"
            + self.origin
            + "/cases\n\nSynthetic local demonstration. No reply is monitored.\n"
        )
        return msg

    def send(self, msg):
        with smtplib.SMTP("127.0.0.1", 1025, timeout=5) as smtp:
            smtp.send_message(msg)

    def once(self):
        leased = self.jobs.lease()
        if not leased:
            return "idle"
        job, token = leased
        now = utc_now()
        user = self.db.users.find_one(
            {"_id": job["recipient_user_id"], "account_status": "active"}, {"verified_contact": 1}
        )
        expired = job.get("expires_at", job["created_at"] + timedelta(hours=24)) <= now
        if not user or expired:
            self.jobs.finish(job["_id"], token, success=False, permanent=True)
            return "discarded"
        try:
            msg = self.message(job, user.get("verified_contact", ""))
        except ValueError:
            self.jobs.finish(job["_id"], token, success=False, permanent=True)
            return "discarded"
        self.jobs.require(None)
        if not self.db.users.find_one(
            {"_id": job["recipient_user_id"], "account_status": "active"}, {"_id": 1}
        ):
            return "discarded"
        try:
            self.send(msg)
        except smtplib.SMTPAuthenticationError:
            self.jobs.finish(job["_id"], token, success=False, permanent=True)
            return "discarded"
        except smtplib.SMTPRecipientsRefused as problem:
            permanent = bool(problem.recipients) and all(
                v[0] >= 500 for v in problem.recipients.values()
            )
            self.jobs.finish(job["_id"], token, success=False, permanent=permanent)
            return "discarded" if permanent else "retry"
        except smtplib.SMTPDataError as problem:
            self.jobs.finish(job["_id"], token, success=False, permanent=problem.smtp_code >= 500)
            return "discarded" if problem.smtp_code >= 500 else "retry"
        except (OSError, smtplib.SMTPException):
            self.jobs.finish(job["_id"], token, success=False)
            return "retry"
        # A crash between send and finish can cause duplicate delivery on lease
        # expiry. Stable Message-ID helps correlation, not exactly-once delivery.
        self.jobs.finish(job["_id"], token, success=True)
        return "sent"

    def alerts(self):
        now = utc_now()
        return {
            "dead": self.db.notification_outbox.count_documents({"state": "dead"}),
            "overdue": self.db.notification_outbox.count_documents(
                {
                    "state": {"$in": ["pending", "leased"]},
                    "created_at": {"$lt": now - timedelta(minutes=15)},
                }
            ),
        }


class SMTPDelivery(LocalDelivery):
    """Explicit opt-in authenticated TLS transport; never used by the local runner."""

    def __init__(self, database, principal, settings):
        import ssl

        from app.services.enrolment import contact_address

        if settings.get("APP_ENV") != "production" or settings.get("EMAIL_DELIVERY_ENABLED") != "1":
            raise ValueError("Production delivery needs an explicit operator opt-in.")
        origin = urlsplit(settings.get("APP_BASE_URL", ""))
        if (
            origin.scheme != "https"
            or not origin.hostname
            or origin.path not in {"", "/"}
            or origin.query
            or origin.fragment
            or origin.username
        ):
            raise ValueError("Configure the approved HTTPS application origin.")
        if any(
            "REPLACE_" in str(settings.get(k, ""))
            for k in ["APP_BASE_URL", "SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM"]
        ):
            raise ValueError("Replace all delivery configuration placeholders first.")
        self.db = database
        self.jobs = NotificationJobs(database, principal)
        self.origin = settings["APP_BASE_URL"].rstrip("/")
        self.host = settings.get("SMTP_HOST", "")
        self.security = settings.get("SMTP_SECURITY", "")
        self.port = int(settings.get("SMTP_PORT", "0"))
        if (
            not self.host
            or "/" in self.host
            or any(c.isspace() for c in self.host)
            or self.security not in {"ssl", "starttls"}
            or not 1 <= self.port <= 65535
        ):
            raise ValueError("Configure an authenticated TLS SMTP service.")
        self.username = settings.get("SMTP_USERNAME")
        self.password = settings.get("SMTP_PASSWORD")
        if not self.username or not self.password:
            raise ValueError("SMTP credentials are required.")
        self.sender = contact_address(settings.get("SMTP_FROM"))
        if self.sender.endswith((".invalid", ".test", ".example")):
            raise ValueError("Configure a real approved sender domain.")
        self.tls = ssl.create_default_context()

    def message(self, job, contact):
        from app.services.enrolment import contact_address

        contact = contact_address(contact)
        if (
            contact.endswith((".invalid", ".test", ".example"))
            or job["template_key"] not in TEMPLATES
        ):
            raise ValueError("A verified real notification contact is required.")
        msg = EmailMessage()
        msg["From"] = self.sender
        msg["To"] = contact
        msg["Subject"] = "An update in Student Support"
        msg["Date"] = format_datetime(utc_now())
        event = hashlib.sha256(
            (job["event_key"] + job["recipient_user_id"] + job["channel"]).encode()
        ).hexdigest()
        msg["Message-ID"] = "<" + event + "@" + self.sender.rsplit("@", 1)[1] + ">"
        msg.set_content(
            "There is an update in your Student Support account.\nSign in to view it:\n"
            + self.origin
            + "/cases\n"
        )
        return msg

    def send(self, msg):
        if self.security == "ssl":
            connection = smtplib.SMTP_SSL(self.host, self.port, timeout=10, context=self.tls)
        else:
            connection = smtplib.SMTP(self.host, self.port, timeout=10)
        with connection as smtp:
            if self.security == "starttls":
                smtp.ehlo()
                smtp.starttls(context=self.tls)
                smtp.ehlo()
            smtp.login(self.username, self.password)
            smtp.send_message(msg)
