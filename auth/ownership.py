"""
Ties a plan-generation session_id to the user who created it. This is the
authorization check behind "can this user see this session's plan/history" —
without it, any authenticated user could read any other user's generated
plan just by guessing/observing a session_id (it's a UUID, not secret).

Same SQLite database as users (data/tamreena.db) — see auth/models.py.
"""

import sqlite3
from typing import Optional

from config import DB_PATH

SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS plan_sessions (
        session_id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        goal TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
"""


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db_connection()
    conn.execute(SCHEMA_SQL)
    conn.commit()
    conn.close()


init_db()


def create_session(session_id: str, user_id: int, goal: Optional[str]) -> None:
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO plan_sessions (session_id, user_id, goal) VALUES (?, ?, ?)",
        (session_id, user_id, goal),
    )
    conn.commit()
    conn.close()


def user_owns_session(session_id: str, user_id: int) -> bool:
    conn = get_db_connection()
    row = conn.execute(
        "SELECT 1 FROM plan_sessions WHERE session_id = ? AND user_id = ?",
        (session_id, user_id),
    ).fetchone()
    conn.close()
    return row is not None


def list_sessions_for_user(user_id: int) -> list[dict]:
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT session_id, goal, created_at FROM plan_sessions WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
