"""Atomic submission keys: caller locks the actor before entering this helper."""

from datetime import timedelta
from uuid import uuid4

from app.repositories.core import identifier, utc_now
from app.services.transactions import VersionConflict


def idempotent(database, sid, actor, operation, key_hash, payload_hash, create):
    if operation not in {"create_case", "send_message"}:
        raise ValueError("Invalid operation.")
    now = utc_now()
    query = {"user_id": identifier(actor), "operation": operation, "key_hash": key_hash}
    previous = database.submission_keys.find_one(query, session=sid)
    if previous:
        if previous["expires_at"] <= now or previous.get("payload_hash") != payload_hash:
            raise VersionConflict("The submission key cannot be reused for different content.")
        return previous["result_id"]
    result = identifier(create())
    database.submission_keys.insert_one(
        {
            "_id": str(uuid4()),
            **query,
            "payload_hash": payload_hash,
            "result_id": result,
            "expires_at": now + timedelta(hours=24),
        },
        session=sid,
    )
    return result
