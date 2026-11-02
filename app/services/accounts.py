"""Own-profile changes and explicitly enabled synthetic OIDC student enrolment."""

from uuid import uuid4

from pymongo.errors import DuplicateKeyError

from app.repositories.core import identifier, utc_now
from app.services.audit import AuditWriter
from app.services.policy import AccessDenied
from app.services.transactions import VersionConflict, transaction

LOCAL_ISSUER = "http://127.0.0.1:8180/realms/student-support"
PROFILE_FIELDS = {"display_name", "course_label"}


def profile_errors(values):
    errors = {}
    for field in PROFILE_FIELDS:
        value = values.get(field, "")
        if not isinstance(value, str) or len(value.strip()) > 160:
            errors[field] = "Use 160 characters or fewer."
        elif any(ord(c) < 32 or ord(c) == 127 for c in value):
            errors[field] = "Remove line breaks and unsupported control characters."
        elif field == "display_name" and not value.strip():
            errors[field] = "Enter the name you would like us to use."
    return errors


class Accounts:
    def __init__(self, database):
        self.db = database

    def resolve(self, issuer, claims, *, allow_registration=False):
        """Call only after OIDC signature/claims validation; never trust provider roles."""
        subject = claims.get("sub")
        if not isinstance(subject, str) or not 1 <= len(subject) <= 255:
            raise ValueError("Invalid verified identity.")
        query = {"identity_issuer": issuer, "identity_subject": subject}

        def operation(sid):
            user = self.db.users.find_one(query, session=sid)
            if user:
                if user["account_status"] != "active":
                    raise AccessDenied("Account unavailable.")
                return user
            if not allow_registration or issuer != LOCAL_ISSUER:
                raise AccessDenied("Account unavailable.")
            key = str(uuid4())
            # Provider contact/role/group/student-ID claims never grant access or
            # become a notification destination. All contacts stay reserved/local.
            name = claims.get("name")
            if not isinstance(name, str) or profile_errors({"display_name": name}):
                name = "New student"
            user = {
                "_id": key,
                **query,
                "display_name": name.strip(),
                "account_status": "active",
                "global_roles": ["student"],
                "authorization_revision": 0,
                "profile_version": 0,
                "student_reference": "DEMO-" + key.replace("-", "").upper(),
                "verified_contact": "student-" + key.replace("-", "") + "@example.invalid",
                "created_at": utc_now(),
            }
            self.db.users.insert_one(user, session=sid)
            AuditWriter(self.db).append(key, "account_created", "user", key, [], sid)
            return user

        try:
            return transaction(self.db, operation)
        except DuplicateKeyError:
            # Concurrent validated first logins converge on the unique issuer/sub.
            user = self.db.users.find_one(query)
            if not user or user["account_status"] != "active":
                raise AccessDenied("Account unavailable.") from None
            return user

    def read(self, actor):
        def operation(sid):
            user = self.db.users.find_one(
                {"_id": identifier(actor), "account_status": "active"}, session=sid
            )
            if not user:
                raise AccessDenied("Account unavailable.")
            AuditWriter(self.db).append(actor, "profile_read", "user", actor, [], sid)
            return {
                k: user[k]
                for k in [
                    "display_name",
                    "course_label",
                    "student_reference",
                    "verified_contact",
                    "profile_version",
                ]
                if k in user
            }

        return transaction(self.db, operation)

    def update(self, actor, version, values):
        if set(values) != PROFILE_FIELDS or profile_errors(values):
            raise ValueError("Invalid profile fields.")
        if type(version) is not int or version < 0:
            raise ValueError("Invalid profile version.")

        def operation(sid):
            user = self.db.users.find_one(
                {"_id": identifier(actor), "account_status": "active"}, session=sid
            )
            if not user:
                raise AccessDenied("Account unavailable.")
            if user.get("profile_version", 0) != version:
                raise VersionConflict("Profile changed; refresh and review your changes.")
            changes = {
                "$set": {
                    "display_name": values["display_name"].strip(),
                    "profile_updated_at": utc_now(),
                },
                "$inc": {"profile_version": 1, "guard_version": 1},
            }
            course = values["course_label"].strip()
            if course:
                changes["$set"]["course_label"] = course
            else:
                changes["$unset"] = {"course_label": ""}
            self.db.users.update_one({"_id": actor}, changes, session=sid)
            AuditWriter(self.db).append(
                actor, "profile_updated", "user", actor, sorted(PROFILE_FIELDS), sid
            )

        transaction(self.db, operation)
