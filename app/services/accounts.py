"""Verified university enrolment and current-user profile management."""

from uuid import uuid4

from flask import current_app, has_app_context
from pymongo.errors import DuplicateKeyError

from app.repositories.core import identifier, utc_now
from app.services.account_privacy import fingerprint
from app.services.audit import AuditWriter
from app.services.enrolment import Enrolment, contact_address
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
    def __init__(self, database, settings=None):
        self.db = database
        self.settings = (
            settings if settings is not None else (current_app.config if has_app_context() else {})
        )

    def resolve(self, issuer, claims, *, allow_registration=False, invitation_hash=None):
        """Call only after OIDC signature/claims validation; never trust provider roles."""
        subject = claims.get("sub")
        if not isinstance(subject, str) or not 1 <= len(subject) <= 255:
            raise ValueError("Invalid verified identity.")
        query = {"identity_issuer": issuer, "identity_subject": subject}

        identity_key = self.settings.get("IDENTITY_FINGERPRINT_KEY")
        if not identity_key:
            raise AccessDenied("Identity-protection configuration is required for account lookup.")
        identity_hash = fingerprint(issuer, subject, identity_key) if identity_key else None
        identity_hashes = [
            fingerprint(issuer, subject, k)
            for k in [identity_key, *self.settings.get("IDENTITY_FINGERPRINT_PREVIOUS_KEYS", [])]
            if k
        ]
        mode = self.settings.get("ENROLMENT_MODE", "preprovisioned")
        if invitation_hash and mode not in {"invitation", "local_demo"}:
            raise AccessDenied("Invitation enrolment is not enabled.")

        def operation(sid):
            if identity_hash and self.db.users.find_one(
                {"identity_fingerprint": {"$in": identity_hashes}, "account_status": "closed"},
                session=sid,
            ):
                raise AccessDenied("This platform account is closed.")
            invite = (
                Enrolment(self.db).pending(invitation_hash, issuer, claims, sid)
                if invitation_hash
                else None
            )
            user = self.db.users.find_one(query, session=sid)
            if user:
                if user["account_status"] != "active":
                    raise AccessDenied("Account unavailable.")
                if mode == "invitation":
                    if claims.get("email_verified") is not True:
                        raise AccessDenied("A verified contact is required.")
                    contact = contact_address(claims.get("email"))
                    if user.get("verified_contact") != contact:
                        self.db.users.update_one(
                            {"_id": user["_id"]},
                            {"$set": {"verified_contact": contact}},
                            session=sid,
                        )
                        AuditWriter(self.db).append(
                            user["_id"],
                            "verified_contact_changed",
                            "user",
                            user["_id"],
                            ["verified_contact"],
                            sid,
                        )
                    user["verified_contact"] = contact
                if invite:
                    Enrolment(self.db).accept(invite, user, sid, new_account=False)
                return user
            if not invite and (
                not allow_registration
                or issuer != LOCAL_ISSUER
                or self.db.name not in {"student_support_dev", "student_support_test"}
            ):
                raise AccessDenied("Account unavailable.")
            key = str(uuid4())
            # Roles/student IDs never come from unchecked provider claims. A real
            # contact is used only after invitation + email_verified validation.
            name = claims.get("name")
            if not isinstance(name, str) or profile_errors({"display_name": name}):
                name = "New student"
            user = {
                "_id": key,
                **query,
                "display_name": name.strip(),
                "account_status": "active",
                "global_roles": ["student"] if not invite or invite["role"] == "student" else [],
                "authorization_revision": 0,
                "profile_version": 0,
                "student_reference": "DEMO-" + key.replace("-", "").upper(),
                "verified_contact": "student-" + key.replace("-", "") + "@example.invalid",
                "created_at": utc_now(),
            }
            if self.settings.get("PORTAL_KIND", "general") != "general" and not invite:
                user["student_reference"] = "SSU-" + key.replace("-", "").upper()
                user.pop("verified_contact", None)
                if claims.get("email_verified") is True:
                    user["verified_contact"] = contact_address(claims.get("email"))
            if identity_hash:
                user["identity_fingerprint"] = identity_hash
            if invite:
                user["verified_contact"] = contact_address(claims["email"])
                user["student_reference"] = "SSU-" + key.replace("-", "").upper()
            self.db.users.insert_one(user, session=sid)
            if invite:
                Enrolment(self.db).accept(invite, user, sid, new_account=True)
            AuditWriter(self.db).append(key, "account_created", "user", key, [], sid)
            return user

        try:
            return transaction(self.db, operation)
        except DuplicateKeyError:
            if invitation_hash:
                raise AccessDenied("Invitation was already used; sign in normally.") from None
            if identity_hash and self.db.users.find_one(
                {"identity_fingerprint": {"$in": identity_hashes}, "account_status": "closed"}
            ):
                raise AccessDenied("This platform account is closed.") from None
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
