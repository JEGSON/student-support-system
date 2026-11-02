"""Run generic notifications only against local Mailpit capture."""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import dotenv_values

from app.repositories.fixtures import fixture_id
from scripts.database_setup import ROOT, local_client
from worker.delivery import LocalDelivery


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", choices=["development", "testing"], default="development")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    values = dotenv_values(ROOT / ".env")
    if values.get("APP_ENV") != "development":
        raise ValueError("Local capture only.")
    kind = "worker_development" if args.environment == "development" else "worker"
    with local_client(values, kind) as client:
        db = client[
            "student_support_dev" if args.environment == "development" else "student_support_test"
        ]
        worker = LocalDelivery(db, fixture_id("worker"), values["APP_BASE_URL"])
        while True:
            outcome = worker.once()
            print("notification_" + outcome, flush=True)
            if args.once:
                print(worker.alerts())
                break
            time.sleep(1 if outcome == "idle" else 0.1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception:
        raise SystemExit("Local worker stopped safely; sensitive details suppressed.") from None
