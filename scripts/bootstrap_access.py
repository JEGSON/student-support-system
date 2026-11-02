"""Trusted offline, synthetic-only paired bootstrap; no HTTP entry point."""

import argparse
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import dotenv_values

from app.repositories.core import identifier, plain_text, utc_now
from app.services.access import PRIVILEGED, AccessService
from app.services.policy import AccessDenied
from scripts.database_setup import ROOT, local_client


def bootstrap(database, administrator, approver, reason):
    if database.name not in {"student_support_dev", "student_support_test"}:
        raise AccessDenied("Synthetic local bootstrap only.")
    identifier(administrator)
    identifier(approver)
    reason = plain_text(reason, 1000)
    if administrator == approver:
        raise AccessDenied("Two independent accounts are required.")
    service = AccessService(database)

    def operation(sid):
        for target in (administrator, approver):
            user = database.users.find_one(
                {"_id": target, "account_status": "active", "fixture_version": "synthetic-v1"},
                session=sid,
            )
            if (
                not user
                or set(user["global_roles"]) & PRIVILEGED
                or user["identity_subject"].startswith("synthetic-placeholder:")
            ):
                raise AccessDenied(
                    "Explicitly provision two unprivileged synthetic identities first."
                )
        for target, role, other in [
            (administrator, "administrator", approver),
            (approver, "access_approver", administrator),
        ]:
            database.privileged_grants.insert_one(
                {
                    "_id": str(uuid4()),
                    "user_id": target,
                    "role": role,
                    "requested_by": target,
                    "approved_by": other,
                    "reason": reason,
                    "decision_reason": "Trusted offline synthetic bootstrap: " + reason[:900],
                    "state": "approved",
                    "created_at": utc_now(),
                    "decided_at": utc_now(),
                },
                session=sid,
            )
            database.users.update_one(
                {"_id": target}, {"$addToSet": {"global_roles": role}}, session=sid
            )
            service.invalidate(target, sid)
            service.audit(
                other, "offline_synthetic_bootstrap", "user", target, ["global_roles"], sid
            )

    service.transaction(operation)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--administrator", required=True)
    parser.add_argument("--approver", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--environment", choices=["development", "testing"], required=True)
    args = parser.parse_args()
    values = dotenv_values(ROOT / ".env")
    if values.get("APP_ENV") != "development":
        raise AccessDenied("Development tooling only.")
    with local_client(values, args.environment) as client:
        bootstrap(
            client[
                "student_support_dev"
                if args.environment == "development"
                else "student_support_test"
            ],
            args.administrator,
            args.approver,
            args.reason,
        )
    print("Synthetic paired bootstrap committed and audited. Re-authenticate to use new contexts.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Bootstrap refused or unavailable. No sensitive details printed."
        ) from None
