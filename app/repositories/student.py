"""Fixed ownership filters and projections for student case queries."""

from app.repositories.core import identifier

LIST_FIELDS = {
    "_id": 1,
    "reference": 1,
    "category": 1,
    "status": 1,
    "created_at": 1,
    "updated_at": 1,
}
DETAIL_FIELDS = {
    **LIST_FIELDS,
    "description": 1,
    "student_id": 1,
    "archive_state": 1,
    "team_id": 1,
    "assignee_id": 1,
}


class StudentCaseRepository:
    def __init__(self, database):
        self.db = database

    def page(self, actor, after, sid):
        query = {"student_id": identifier(actor), "archive_state": "active"}
        if after:
            stamp, key = after
            query["$or"] = [
                {"updated_at": {"$lt": stamp}},
                {"updated_at": stamp, "_id": {"$lt": identifier(key)}},
            ]
        return list(
            self.db.cases.find(query, LIST_FIELDS, session=sid, max_time_ms=1500)
            .sort([("updated_at", -1), ("_id", -1)])
            .limit(21)
        )

    def own(self, actor, case_id, sid):
        return self.db.cases.find_one(
            {
                "_id": identifier(case_id),
                "student_id": identifier(actor),
                "archive_state": "active",
            },
            DETAIL_FIELDS,
            session=sid,
            max_time_ms=1500,
        )

    def insert(self, record, event, sid):
        self.db.cases.insert_one(record, session=sid)
        self.db.case_events.insert_one(event, session=sid)
