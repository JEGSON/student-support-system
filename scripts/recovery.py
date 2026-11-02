"""Encrypted local synthetic backup/ledger and quarantined restore commands."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cryptography.fernet import Fernet
from dotenv import dotenv_values

from app.operations.recovery import capture, private_write, restore
from app.repositories.schema import install_schema
from scripts.database_setup import ROOT, local_client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["keygen", "backup", "ledger", "restore"])
    parser.add_argument("--key", required=True)
    parser.add_argument("--output")
    parser.add_argument("--input")
    parser.add_argument("--ledger")
    parser.add_argument("--environment", choices=["development", "testing"], default="development")
    parser.add_argument("--ack-latest-ledger", action="store_true")
    args = parser.parse_args()
    paths = [Path(p).resolve() for p in [args.key, args.output, args.input, args.ledger] if p]
    if not all(p.is_relative_to(ROOT / "runtime") for p in paths):
        raise ValueError("Local recovery files must stay in ignored runtime storage.")
    if args.action == "keygen":
        private_write(args.key, Fernet.generate_key())
        print("Private recovery key generated. Store separately from snapshots.")
        return
    values = dotenv_values(ROOT / ".env")
    if values.get("APP_ENV") != "development":
        raise ValueError("Local synthetic tooling only.")
    key = Path(args.key).read_bytes()
    if args.action == "restore":
        if not args.ack_latest_ledger:
            raise ValueError("Verify the latest authoritative disposal ledger before restore.")
        with local_client(values, "schema") as client:
            install_schema(client.student_support_restore_test)
        with local_client(values, "restore") as client:
            result = restore(client.student_support_restore_test, key, args.input, args.ledger)
    else:
        with local_client(values, args.environment) as client:
            result = capture(
                client[
                    "student_support_dev"
                    if args.environment == "development"
                    else "student_support_test"
                ],
                key,
                args.output,
                args.action == "ledger",
            )
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Recovery command refused or failed. Keep quarantine offline; sensitive details suppressed."
        ) from None
