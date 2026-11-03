"""Operator-owned encrypted backups and offline production restore rehearsals."""

import argparse
import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pymongo import MongoClient

from app.config import load_config
from app.operations.recovery import capture, restore
from app.repositories.schema import install_schema
from scripts.production_setup import operator_uri


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["backup", "ledger", "restore"])
    parser.add_argument("--file", required=True)
    parser.add_argument("--ledger")
    parser.add_argument("--quarantine")
    parser.add_argument("--ack-latest-ledger", action="store_true")
    parser.add_argument("--ack-production-maintenance", action="store_true")
    args = parser.parse_args()
    settings = load_config()
    if settings["APP_ENV"] != "production" or not args.ack_production_maintenance:
        raise ValueError("Production operator acknowledgement required.")
    key_path = Path(os.environ["BACKUP_KEY_FILE"]).resolve()
    directory = Path(os.environ["BACKUP_DIRECTORY"]).resolve()
    if stat.S_IMODE(key_path.stat().st_mode) & 0o077:
        raise ValueError("Protect the mounted backup key from group/other access.")
    key = key_path.read_bytes()
    file = (directory / args.file).resolve()
    ledger = (directory / args.ledger).resolve() if args.ledger else None
    if (
        not file.is_relative_to(directory)
        or (ledger and not ledger.is_relative_to(directory))
        or key_path.is_relative_to(directory)
    ):
        raise ValueError("Keep backup paths contained and keys in separate storage.")
    if args.action != "restore":
        with MongoClient(
            operator_uri("MONGODB_BACKUP_URI"), tz_aware=True, serverSelectionTimeoutMS=5000
        ) as client:
            capture(
                client[settings["MONGODB_DATABASE"]],
                key,
                file,
                args.action == "ledger",
                allow_production=True,
            )
        print(
            "Encrypted " + args.action + " created privately. Copy to approved independent storage."
        )
    else:
        if (
            not args.ack_latest_ledger
            or not ledger
            or not args.quarantine
            or not args.quarantine.startswith("student_support_restore_")
            or args.quarantine == settings["MONGODB_DATABASE"]
        ):
            raise ValueError(
                "Select an offline quarantine and the latest independently verified ledger."
            )
        with MongoClient(operator_uri("MONGODB_SCHEMA_URI"), tz_aware=True) as client:
            install_schema(client[args.quarantine], allow_production=True)
        with MongoClient(operator_uri("MONGODB_RESTORE_URI"), tz_aware=True) as client:
            outcome = restore(
                client[args.quarantine], key, file, ledger, quarantine=args.quarantine
            )
        print(outcome)
        print("Quarantine remains offline. No live activation performed.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Production recovery refused or unavailable; sensitive details suppressed."
        ) from None
