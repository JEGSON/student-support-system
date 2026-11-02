"""Explicit local routing for the five labelled synthetic support teams."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import dotenv_values

from app.repositories.fixtures import fixture_id
from app.repositories.schema import CATEGORIES
from scripts.database_setup import ROOT, local_client


def main():
    values = dotenv_values(ROOT / ".env")
    if values.get("APP_ENV") != "development":
        raise ValueError("Local synthetic setup only.")
    mapping = {name: fixture_id("team_" + name) for name in CATEGORIES}
    with local_client(values, "development") as client:
        for category, team in mapping.items():
            if not client.student_support_dev.teams.find_one(
                {
                    "_id": team,
                    "active": True,
                    "category_scope": category,
                    "fixture_version": "synthetic-v1",
                }
            ):
                raise ValueError("Seed all five synthetic teams first.")
    if "CASE_ROUTING_JSON" not in values:
        with (ROOT / ".env").open("a") as stream:
            stream.write("\nCASE_ROUTING_JSON=" + json.dumps(mapping, separators=(",", ":")) + "\n")
        (ROOT / ".env").chmod(0o600)
        print("Explicit five-category local routing configured.")
    else:
        print("Existing routing preserved. Review CASE_ROUTING_JSON before changing it.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Local routing setup failed; no sensitive details printed.") from None
