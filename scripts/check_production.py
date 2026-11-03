"""Sanitised operator readiness checks; never establishes policy approval itself."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pymongo import MongoClient

from app.config import ConfigurationError, load_config
from app.repositories.schema import CATEGORIES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration-only", action="store_true")
    args = parser.parse_args()
    try:
        settings = load_config()
        if settings["APP_ENV"] != "production":
            raise ConfigurationError("Select the production environment explicitly.")
    except ConfigurationError as problem:
        print(json.dumps({"configuration_valid": False, "reason": str(problem)}))
        return 1
    report = {
        "configuration_valid": True,
        "externally_verified": False,
        "notes": "Operator policy acknowledgement is not an independent legal, accessibility or security approval.",
    }
    if not args.configuration_only:
        with MongoClient(
            settings["MONGODB_URI"], tz_aware=True, serverSelectionTimeoutMS=5000
        ) as client:
            database = client[settings["MONGODB_DATABASE"]]
            database.command("ping")
            routed = {
                c
                for team in database.teams.find({"active": True}, {"routing_categories": 1})
                for c in team.get("routing_categories", [])
            }
            report["missing_intake_categories"] = sorted(set(CATEGORIES) - routed)
            report["unreviewed_closures"] = database.account_closures.count_documents(
                {"state": "review_required"}
            )
            report["dead_notifications"] = database.notification_outbox.count_documents(
                {"state": "dead"}
            )
            report["bootstrap_present"] = bool(
                database.users.find_one(
                    {"account_status": "active", "global_roles": "administrator"}, {"_id": 1}
                )
            )
            report["database_ready"] = (
                not report["missing_intake_categories"] and report["bootstrap_present"]
            )
    print(json.dumps(report, indent=2))
    return 0 if args.configuration_only or report["database_ready"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit("Readiness check failed; connection details suppressed.") from None
