"""Bounded shared MongoDB transactions. Only database work belongs in callbacks."""

from pymongo import timeout
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern


class VersionConflict(ValueError):
    pass


def transaction(database, operation):
    with timeout(5), database.client.start_session() as sid:
        return sid.with_transaction(
            operation,
            read_concern=ReadConcern("snapshot"),
            write_concern=WriteConcern("majority"),
            max_commit_time_ms=1500,
        )
