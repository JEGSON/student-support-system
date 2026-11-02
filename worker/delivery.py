"""Isolated SMTP capture delivery. No production/external transport is enabled."""

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
        try:
            self.send(msg)
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
