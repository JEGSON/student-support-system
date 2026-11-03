"""Opt-in production generic notification worker; settings injected by the operator."""

import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pymongo import MongoClient

from app.repositories.core import identifier
from worker.delivery import SMTPDelivery


def main():
    settings = dict(os.environ)
    if settings.get("APP_ENV") != "production" or settings.get("EMAIL_DELIVERY_ENABLED") != "1":
        raise ValueError("No production delivery was authorised by configuration.")
    database = settings.get("MONGODB_DATABASE", "")
    uri = settings.get("MONGODB_WORKER_URI", "")
    if (
        not re.fullmatch(r"[a-z][a-z0-9_]{2,62}", database)
        or database.startswith("student_support_restore_")
        or database in {"admin", "local", "config", "student_support_dev", "student_support_test"}
    ):
        raise ValueError("A separate production database is required.")
    options = [(k.casefold(), v.casefold()) for k, v in parse_qsl(urlsplit(uri).query)]
    if len(dict(options)) != len(options):
        raise ValueError("Duplicate database options are not allowed.")
    options = dict(options)
    if (
        not uri.startswith(("mongodb://", "mongodb+srv://"))
        or options.get("tls", "true" if uri.startswith("mongodb+srv://") else "false") != "true"
        or any(
            options.get(k, "false") != "false"
            for k in ["tlsinsecure", "tlsallowinvalidcertificates", "tlsallowinvalidhostnames"]
        )
    ):
        raise ValueError("Verified database TLS is required.")
    principal = identifier(settings.get("NOTIFICATION_PRINCIPAL_ID"))
    with MongoClient(
        uri, tz_aware=True, serverSelectionTimeoutMS=5000, socketTimeoutMS=10000, maxPoolSize=10
    ) as client:
        delivery = SMTPDelivery(client[database], principal, settings)
        while True:
            outcome = delivery.once()
            print("notification_" + outcome, flush=True)
            print(delivery.alerts(), flush=True)
            if "--once" in sys.argv[1:]:
                break
            time.sleep(1 if outcome == "idle" else 0.1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception:
        raise SystemExit(
            "Production worker stopped safely; sensitive details suppressed."
        ) from None
