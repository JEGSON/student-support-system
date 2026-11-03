"""Operator-only production schema/bootstrap/disposal; no provider or hosting creation."""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pymongo import MongoClient

from app.config import load_config
from app.operations.bootstrap import bootstrap_service
from app.repositories.schema import install_schema
from app.services.lifecycle import Lifecycle


def operator_uri(name):
    uri = os.environ.get(name, "")
    if not uri.startswith(("mongodb://", "mongodb+srv://")):
        raise ValueError("Configure the restricted operator URI.")
    pairs = [(k.casefold(), v.casefold()) for k, v in parse_qsl(urlsplit(uri).query)]
    options = dict(pairs)
    if (
        len(options) != len(pairs)
        or options.get("tls", "true" if uri.startswith("mongodb+srv://") else "false") != "true"
        or any(
            options.get(k, "false") != "false"
            for k in ["tlsinsecure", "tlsallowinvalidcertificates", "tlsallowinvalidhostnames"]
        )
    ):
        raise ValueError("Verified operator database TLS is required.")
    return uri


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["schema", "bootstrap", "dispose"])
    parser.add_argument("--ack-production-maintenance", action="store_true")
    parser.add_argument("--record")
    args = parser.parse_args()
    settings = load_config()
    if settings["APP_ENV"] != "production" or not args.ack_production_maintenance:
        raise ValueError("Explicit production maintenance acknowledgement is required.")
    kind = "MONGODB_SCHEMA_URI" if args.action == "schema" else "MONGODB_MAINTENANCE_URI"
    with MongoClient(
        operator_uri(kind), tz_aware=True, serverSelectionTimeoutMS=5000, socketTimeoutMS=10000
    ) as client:
        database = client[settings["MONGODB_DATABASE"]]
        if args.action == "schema":
            print(
                "Production collection contracts installed:",
                install_schema(database, allow_production=True),
            )
        elif args.action == "bootstrap":
            # Personal identity metadata is provided on stdin, never shell argv/logs.
            raw = sys.stdin.buffer.read(16385)
            if len(raw) > 16384:
                raise ValueError("Bootstrap input exceeds bound.")
            people = json.loads(raw)
            if set(people) != {"administrator", "approver"}:
                raise ValueError("Supply the two approved identities.")
            if any(
                "REPLACE_" in str(value) for person in people.values() for value in person.values()
            ):
                raise ValueError("Use verified identity metadata, not template placeholders.")
            if any(
                person.get("verified_contact", "")
                .casefold()
                .endswith((".invalid", ".test", ".example"))
                for person in people.values()
            ):
                raise ValueError(
                    "Supply independently verified real university contacts for production bootstrap."
                )
            result = bootstrap_service(
                database, settings["OIDC_ISSUER"], people["administrator"], people["approver"]
            )
            print(json.dumps(result))
        else:
            if not args.record:
                raise ValueError("Select an independently approved disposal record.")
            Lifecycle(database, settings).execute(args.record)
            print("Approved disposal completed or already completed; no narratives printed.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Production maintenance refused or unavailable; sensitive details suppressed."
        ) from None
