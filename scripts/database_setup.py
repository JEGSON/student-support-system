"""Explicit local schema migration/fixture setup. No public runtime schema mutation."""

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import dotenv_values
from pymongo import MongoClient

from app.repositories.fixtures import reset_fixtures, seed_fixtures
from app.repositories.schema import install_schema

ROOT = Path(__file__).resolve().parents[1]


def local_client(values, kind):
    user, key = {
        "schema": ("support_schema", "MONGO_SCHEMA_PASSWORD"),
        "development": ("support_fixture", "MONGO_FIXTURE_PASSWORD"),
        "web_development": ("support_app", "MONGO_APP_PASSWORD"),
        "web_testing": ("support_web_test", "MONGO_WEB_TEST_PASSWORD"),
        "audit": ("support_audit_test", "MONGO_AUDIT_TEST_PASSWORD"),
        "audit_development": ("support_audit", "MONGO_AUDIT_PASSWORD"),
        "worker": ("support_worker_test", "MONGO_WORKER_TEST_PASSWORD"),
        "worker_development": ("support_worker", "MONGO_WORKER_PASSWORD"),
        "testing": ("support_test", "MONGO_TEST_PASSWORD"),
    }[kind]
    secret = values.get(key)
    if not secret or secret.startswith("REPLACE_"):
        raise ValueError("Generate the required local secret first.")
    return MongoClient(
        f"mongodb://{user}:{quote(secret, safe='')}@localhost:27017/admin?replicaSet=rs0&directConnection=true",
        tz_aware=True,
        serverSelectionTimeoutMS=2000,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=["development", "testing"], required=True)
    parser.add_argument("--seed", action="store_true")
    parser.add_argument(
        "--reset-synthetic",
        action="store_true",
        help="Explicitly remove only synthetic-v1 labelled records before reseeding",
    )
    args = parser.parse_args()
    values = dotenv_values(ROOT / ".env")
    name = "student_support_dev" if args.environment == "development" else "student_support_test"
    with local_client(values, "schema") as client:
        count = install_schema(client[name])
    with local_client(values, args.environment) as client:
        if args.reset_synthetic:
            reset_fixtures(client[name])
        if args.seed:
            seed_fixtures(client[name], values["OIDC_ISSUER"])
    print(
        f"Local {args.environment} schema v1 ready: {count} collection contracts. Synthetic fixture action completed if requested."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Local database setup failed. No connection or credential details printed."
        ) from None
