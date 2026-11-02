"""Signed, scope-bound thread cursors and controlled service result presentation."""

from datetime import datetime

from flask import g, request

from app.cases.routes import signer
from app.repositories.core import identifier


def cursor(case_id, kind):
    raw = request.args.get(kind)
    if not raw:
        return None
    if len(raw) > 1000:
        raise ValueError("Invalid cursor.")
    data = signer("conversation-page-v1").loads(raw, max_age=3600)
    if data["user"] != g.user["_id"] or data["case"] != case_id or data["kind"] != kind:
        raise ValueError("Invalid cursor.")
    stamp = datetime.fromisoformat(data["stamp"])
    if stamp.tzinfo is None:
        raise ValueError("Invalid cursor.")
    return stamp, identifier(data["id"])


def encode_cursor(case_id, kind, value):
    return (
        signer("conversation-page-v1").dumps(
            {
                "user": g.user["_id"],
                "case": case_id,
                "kind": kind,
                "stamp": value[0].isoformat(),
                "id": value[1],
            }
        )
        if value
        else None
    )
