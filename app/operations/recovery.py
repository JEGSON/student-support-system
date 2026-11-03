"""Bounded authenticated backups and explicitly quarantined restoration."""

import gzip
import os
from pathlib import Path

from bson import json_util
from cryptography.fernet import Fernet
from pymongo import timeout
from pymongo.read_concern import ReadConcern

from app.repositories.core import utc_now
from app.repositories.schema import SCHEMAS
from app.services.account_privacy import redact_principal
from app.services.lifecycle import erase_linked
from app.services.transactions import transaction

EXCLUDED = {"sessions", "auth_attempts", "submission_keys", "rate_limits"}
MAX_BYTES = 200 * 1024 * 1024


def private_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)


def capture(database, key, destination, ledger_only=False, *, allow_production=False):
    if (
        database.name not in {"student_support_dev", "student_support_test"}
        and not allow_production
    ):
        raise ValueError("Production backup requires an explicit operator command.")
    if database.name in {"admin", "config", "local"} or database.name.startswith(
        "student_support_restore_"
    ):
        raise ValueError("Select the source application database.")
    captured = utc_now()
    with timeout(45), database.client.start_session() as sid:
        with sid.start_transaction(read_concern=ReadConcern("snapshot")):
            if ledger_only:
                data = {
                    "kind": "disposal-ledger",
                    "captured_at": captured,
                    "account_closures": list(database.account_closures.find({}, session=sid)),
                    "records": list(
                        database.disposal_records.find({"state": "completed"}, session=sid)
                    ),
                }
            else:
                data = {
                    "kind": "student-support-backup-v2"
                    if allow_production
                    else "synthetic-backup-v1",
                    "source_database": database.name,
                    "captured_at": captured,
                    "collections": {
                        name: list(database[name].find({}, session=sid))
                        for name in SCHEMAS
                        if name not in EXCLUDED
                    },
                }
    raw = json_util.dumps(data).encode()
    if len(raw) > MAX_BYTES:
        raise ValueError("Snapshot exceeds the reviewed demonstration bound.")
    private_write(destination, Fernet(key).encrypt(gzip.compress(raw)))
    return {
        "captured_at": captured.isoformat(),
        "plaintext_bytes": len(raw),
        "encrypted_bytes": Path(destination).stat().st_size,
    }


def decode(path, key):
    if Path(path).stat().st_size > MAX_BYTES * 2:
        raise ValueError("Backup exceeds bound.")
    compressed = Fernet(key).decrypt(Path(path).read_bytes())
    import io

    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Expanded backup exceeds bound.")
    return json_util.loads(raw.decode(), json_options=json_util.JSONOptions(tz_aware=True))


def restore(database, key, backup_path, ledger_path, *, quarantine=None):
    if database.name != "student_support_restore_test" and (
        database.name != quarantine or not database.name.startswith("student_support_restore_")
    ):
        raise ValueError("Only an explicit quarantined restore database is allowed.")
    backup = decode(backup_path, key)
    ledger = decode(ledger_path, key)
    if (
        backup.get("kind") not in {"synthetic-backup-v1", "student-support-backup-v2"}
        or ledger.get("kind") != "disposal-ledger"
        or ledger["captured_at"] < backup["captured_at"]
    ):
        raise ValueError("A current authenticated disposal ledger is required.")
    if database.name != "student_support_restore_test" and (
        backup.get("kind") != "student-support-backup-v2"
        or backup.get("source_database") == database.name
    ):
        raise ValueError("Production restore must be a separate quarantine image.")
    if not set(backup["collections"]) <= set(SCHEMAS) - EXCLUDED:
        raise ValueError("Unknown backup collections.")
    if any(database[name].find_one({}) for name in SCHEMAS):
        raise ValueError("Restore target must be empty; no overwrite is authorised.")
    # Commit the restored image, then idempotently reapply the external ledger and
    # suppress jobs. Quarantine must remain offline until the full pass succeeds.
    for name, documents in backup["collections"].items():
        if documents:
            database[name].insert_many(documents, ordered=True)
    return reconcile(
        database, ledger["records"], ledger.get("account_closures", []), quarantine=quarantine
    )


def reconcile(database, records, account_closures=(), *, quarantine=None):
    if database.name != "student_support_restore_test" and (
        database.name != quarantine or not database.name.startswith("student_support_restore_")
    ):
        raise ValueError("Quarantine only.")
    for row in records:
        if row.get("state") != "completed":
            raise ValueError("Invalid completed disposal record.")

        def replay(sid, row=row):
            erase_linked(database, row["case_id"], sid)
            database.disposal_records.replace_one(
                {"_id": row["_id"]}, row, upsert=True, session=sid
            )

        transaction(database, replay)
    for closure in account_closures:
        if closure.get("state") not in {"review_required", "profile_erased", "retained"}:
            raise ValueError("Invalid account-closure ledger.")

        def replay_closure(sid, closure=closure):
            redact_principal(database, closure, sid)
            database.account_closures.replace_one(
                {"_id": closure["_id"]}, closure, upsert=True, session=sid
            )

        transaction(database, replay_closure)
    # Invitation codes from a backup must not regain validity.
    database.enrolment_invitations.update_many({"state": "pending"}, {"$set": {"state": "revoked"}})
    for name in EXCLUDED:
        database[name].delete_many({})
    database.notification_outbox.update_many(
        {"state": {"$in": ["pending", "leased"]}},
        {"$set": {"state": "dead"}, "$unset": {"lease_hash": "", "lease_until": ""}},
    )
    return {
        "disposed_records_replayed": len(records),
        "account_closures_replayed": len(account_closures),
        "sessions": database.sessions.count_documents({}),
        "pending_notifications": database.notification_outbox.count_documents(
            {"state": {"$in": ["pending", "leased"]}}
        ),
    }
