"""
User accounts — SQLite, same database file as the exercise table
(data/tamreena.db). A separate users database isn't warranted at this
stage; see docs/CODE_MAP.md for the project's "don't over-engineer for
scale you don't need yet" convention.

Google is the only sign-in method wired up for now (google_sub is NOT NULL).
If email/password or another provider is added later, google_sub should
become nullable and a `provider` column should distinguish rows.
"""

import sqlite3
from typing import Optional

from config import DB_PATH

SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        google_sub TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        name TEXT,
        picture_url TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
"""


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Idempotent — creates the users table if it doesn't exist yet."""
    conn = get_db_connection()
    conn.execute(SCHEMA_SQL)
    conn.commit()
    conn.close()


init_db()


def get_user_by_id(user_id: int) -> Optional[dict]:
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_or_create_user_by_google(sub: str, email: str, name: Optional[str], picture_url: Optional[str]) -> dict:
    """Looks up a user by their stable Google subject ID, creating the row on
    first sign-in. `sub` (not email) is the identity key — Google's own docs
    warn email addresses can be reassigned, sub never is."""
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE google_sub = ?", (sub,)).fetchone()
    if row:
        conn.close()
        return dict(row)

    conn.execute(
        "INSERT INTO users (google_sub, email, name, picture_url) VALUES (?, ?, ?, ?)",
        (sub, email, name, picture_url),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM users WHERE google_sub = ?", (sub,)).fetchone()
    conn.close()
    return dict(row)
