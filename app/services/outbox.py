"""Generic transactional jobs and lease states only; this module never sends email."""

import hashlib
import secrets
from datetime import timedelta
from uuid import uuid4

from pymongo import ReturnDocument

from app.repositories.core import identifier, utc_now
from app.services.policy import AccessDenied, worker_allows
from app.services.transactions import transaction

TEMPLATES = {"case_received", "case_updated", "information_requested", "case_closed"}


class Outbox:
    def __init__(self, database):
        self.db = database

    def enqueue(self, sid, event_key, recipient, case_id, template):
        if template not in TEMPLATES or not isinstance(event_key, str) or len(event_key) > 160:
            raise ValueError("Invalid notification metadata.")
        # Serialize notification intent against account closure/contact revocation.
        if not self.db.users.update_one(
            {"_id": identifier(recipient), "account_status": "active"},
            {"$inc": {"guard_version": 1}},
            session=sid,
        ).matched_count:
            return
        now = utc_now()
        self.db.notification_outbox.insert_one(
            {
                "_id": str(uuid4()),
                "event_key": event_key,
                "recipient_user_id": identifier(recipient),
                "case_id": identifier(case_id),
                "template_key": template,
                "channel": "email",
                "state": "pending",
                "attempts": 0,
                "next_attempt_at": now,
                "created_at": now,
                "expires_at": now + timedelta(hours=24),
            },
            session=sid,
        )


class NotificationJobs:
    def __init__(self, database, principal):
        self.db = database
        self.principal = identifier(principal)

    def require(self, sid):
        principal = self.db.service_principals.find_one({"_id": self.principal}, session=sid)
        if not worker_allows(principal, "lease_notification"):
            raise AccessDenied("Worker access denied.")

    def lease(self):
        token = secrets.token_urlsafe(32)
        now = utc_now()

        def operation(sid):
            self.require(sid)
            self.db.notification_outbox.update_many(
                {"state": "leased", "attempts": {"$gte": 5}, "lease_until": {"$lte": now}},
                {"$set": {"state": "dead"}, "$unset": {"lease_hash": "", "lease_until": ""}},
                session=sid,
            )
            query = {
                "attempts": {"$lt": 5},
                "$or": [
                    {"state": "pending", "next_attempt_at": {"$lte": now}},
                    {"state": "leased", "lease_until": {"$lte": now}},
                ],
            }
            job = self.db.notification_outbox.find_one_and_update(
                query,
                {
                    "$set": {
                        "state": "leased",
                        "lease_until": now + timedelta(seconds=60),
                        "lease_hash": hashlib.sha256(token.encode()).hexdigest(),
                    },
                    "$inc": {"attempts": 1},
                },
                sort=[("next_attempt_at", 1), ("_id", 1)],
                return_document=ReturnDocument.AFTER,
                session=sid,
            )
            return (job, token) if job else None

        return transaction(self.db, operation)

    def finish(self, job_id, token, *, success, permanent=False):
        if type(success) is not bool or type(permanent) is not bool or not isinstance(token, str):
            raise ValueError("Invalid job result.")

        def operation(sid):
            self.require(sid)
            now = utc_now()
            query = {
                "_id": identifier(job_id),
                "state": "leased",
                "lease_until": {"$gt": now},
                "lease_hash": hashlib.sha256(token.encode()).hexdigest(),
            }
            job = self.db.notification_outbox.find_one(query, session=sid)
            if not job:
                raise AccessDenied("Lease expired or unavailable.")
            state = (
                "sent" if success else "dead" if permanent or job["attempts"] >= 5 else "pending"
            )
            self.db.notification_outbox.update_one(
                query,
                {
                    "$set": {
                        "state": state,
                        "next_attempt_at": now
                        + timedelta(seconds=min(3600, 30 * 2 ** job["attempts"])),
                    },
                    "$unset": {"lease_hash": "", "lease_until": ""},
                },
                session=sid,
            )

        transaction(self.db, operation)
