"""Add only the new schema-setup secret to an existing generated local setup."""

import secrets
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def prepare():
    path = ROOT / ".env"
    if not path.exists():
        raise SystemExit("Generate local .env first.")
    existing = dotenv_values(path)
    missing = [
        key
        for key in (
            "MONGO_SCHEMA_PASSWORD",
            "MONGO_RESTORE_PASSWORD",
            "MONGO_FIXTURE_PASSWORD",
            "MONGO_WEB_TEST_PASSWORD",
            "MONGO_AUDIT_PASSWORD",
            "MONGO_AUDIT_TEST_PASSWORD",
            "MONGO_WORKER_PASSWORD",
            "MONGO_WORKER_TEST_PASSWORD",
        )
        if not existing.get(key)
    ]
    if missing:
        with path.open("a") as handle:
            for key in missing:
                handle.write("\n" + key + "=" + secrets.token_urlsafe(48) + "\n")
        path.chmod(0o600)
    print("Local schema secret is prepared; existing credentials preserved.")


if __name__ == "__main__":
    prepare()
