"""Add a stable local identity key without losing prior closure suppression."""

import json
import os
import secrets
import tempfile
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / ".env"
    original = path.read_text()
    values = dotenv_values(path)
    if values.get("APP_ENV") != "development":
        raise ValueError("Local configuration only.")
    if values.get("IDENTITY_FINGERPRINT_KEY"):
        print("Existing identity-protection key preserved.")
        return
    old = values.get("SECRET_KEY", "")
    if len(old) < 48:
        raise ValueError("Existing generated configuration required.")
    with tempfile.NamedTemporaryFile(mode="w", dir=ROOT / "runtime", delete=False) as stream:
        temporary = Path(stream.name)
        os.fchmod(stream.fileno(), 0o600)
        stream.write(
            original.rstrip()
            + "\nIDENTITY_FINGERPRINT_KEY="
            + secrets.token_urlsafe(48)
            + "\nIDENTITY_FINGERPRINT_PREVIOUS_KEYS="
            + json.dumps([old])
            + "\n"
        )
    try:
        if path.read_text() != original:
            raise ValueError("Configuration changed concurrently; retry safely.")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    print("Private identity-protection key added; previous closure key retained. Restart the app.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Local account-key configuration refused; no secrets printed.") from None
