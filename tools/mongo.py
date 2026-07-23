"""
Shared MongoDB client — a single long-lived MongoClient (unlike
sqlite3.connect(), which every SQLite-era module called per-operation,
MongoClient manages its own connection pool internally and is meant to be
constructed once and reused, per pymongo's own docs).
"""

from typing import Optional

from pymongo import ASCENDING, MongoClient
from pymongo.database import Database

from config import MONGO_DB_NAME, MONGO_URI

_client: Optional[MongoClient] = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI)
    return _client


def get_db() -> Database:
    return get_client()[MONGO_DB_NAME]


def ensure_indexes() -> None:
    """Idempotent — call once at app startup (see api/main.py)."""
    db = get_db()

    db.users.create_index("google_sub", unique=True)
    db.users.create_index("email", unique=True)

    db.plan_sessions.create_index([("user_id", ASCENDING), ("created_at", -1)])

    db.exercises.create_index([("primary_muscle", ASCENDING), ("movement_type", ASCENDING)])
    db.exercises.create_index([("name", "text")])

    db.inbody_scans.create_index([("user_id", ASCENDING), ("created_at", -1)])

    db.workout_feedback.create_index([("user_id", ASCENDING), ("submitted_at", -1)])
    db.workout_feedback.create_index([("session_id", ASCENDING), ("submitted_at", -1)])

    db.corrective_results.create_index([("session_id", ASCENDING), ("exercise_id", ASCENDING)])
    db.corrective_results.create_index([("user_id", ASCENDING), ("recorded_at", -1)])
