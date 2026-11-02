"""Execute an independently approved synthetic disposal using offline credentials."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import dotenv_values

from app.services.lifecycle import Lifecycle
from scripts.database_setup import ROOT, local_client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", required=True)
    parser.add_argument("--environment", choices=["development", "testing"], required=True)
    args = parser.parse_args()
    values = dotenv_values(ROOT / ".env")
    if values.get("APP_ENV") != "development":
        raise ValueError("Synthetic local disposal only.")
    with local_client(values, args.environment) as client:
        Lifecycle(
            client[
                "student_support_dev"
                if args.environment == "development"
                else "student_support_test"
            ]
        ).execute(args.record)
    print("Approved synthetic disposal completed or already completed. No narrative printed.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Synthetic disposal refused or unavailable.") from None
