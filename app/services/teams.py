"""Administrator-managed university teams and unique category intake routing."""

from uuid import uuid4

from pymongo.errors import DuplicateKeyError

from app.repositories.core import identifier, plain_text
from app.repositories.schema import CATEGORIES
from app.services.access import AccessService
from app.services.audit import AuditWriter
from app.services.policy import Policy
from app.services.transactions import VersionConflict, transaction


class Teams:
    def __init__(self, database):
        self.db = database

    def list(self, actor, context):
        Policy(self.db, actor, context).require("manage_accounts")
        return list(self.db.teams.find({}).sort([("name", 1), ("_id", 1)]).limit(100))

    def save(
        self, actor, context, name, categories, routing, *, team=None, version=None, active=True
    ):
        name = plain_text(name, 100)
        if (
            any(ord(c) < 32 for c in name)
            or type(active) is not bool
            or not isinstance(categories, list)
            or not categories
            or not all(isinstance(c, str) for c in categories)
            or len(set(categories)) != len(categories)
            or set(categories) - set(CATEGORIES)
            or not isinstance(routing, list)
            or not all(isinstance(c, str) for c in routing)
            or len(set(routing)) != len(routing)
            or set(routing) - set(categories)
            or (routing and not active)
        ):
            raise ValueError("Choose valid team categories and active intake routes.")
        key = identifier(team) if team else str(uuid4())

        def operation(sid):
            Policy(self.db, actor, context, sid).require("manage_accounts")
            AccessService(self.db).touch_user(actor, sid)
            if team:
                current = self.db.teams.find_one({"_id": key}, session=sid)
                if (
                    not current
                    or type(version) is not int
                    or current["authorization_revision"] != version
                ):
                    raise VersionConflict("Team changed; review its current settings.")
                removed = set(current["category_scope"]) - set(categories)
                if (
                    not active and self.db.cases.find_one({"team_id": key}, {"_id": 1}, session=sid)
                ) or (
                    removed
                    and self.db.cases.find_one(
                        {
                            "team_id": key,
                            "archive_state": "active",
                            "category": {"$in": list(removed)},
                        },
                        {"_id": 1},
                        session=sid,
                    )
                ):
                    raise ValueError(
                        "Existing case ownership must remain valid; retain the team/category until those records are handled."
                    )
                update = {
                    "$set": {"name": name, "active": active, "category_scope": categories},
                    "$inc": {"authorization_revision": 1},
                }
                if routing:
                    update["$set"]["routing_categories"] = routing
                else:
                    update["$unset"] = {"routing_categories": ""}
                self.db.teams.update_one({"_id": key}, update, session=sid)
            else:
                record = {
                    "_id": key,
                    "name": name,
                    "active": active,
                    "category_scope": categories,
                    "authorization_revision": 0,
                }
                if routing:
                    record["routing_categories"] = routing
                self.db.teams.insert_one(record, session=sid)
            AuditWriter(self.db).append(
                actor,
                "team_changed",
                "team",
                key,
                ["active", "category_scope", "routing_categories"],
                sid,
            )
            return key

        try:
            return transaction(self.db, operation)
        except DuplicateKeyError:
            raise ValueError(
                "That team name or intake category is already configured. Review the existing team first."
            ) from None
