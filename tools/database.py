"""
Exercise database — SQLite.

MongoDB is the target per tamrena_architecture_2.md Section 8, but this stage
of the project keeps everything on SQLite (data/tamreena.db). Swapping the
backing store later only touches this file — `search_exercise_db` is the
only contract the agents depend on.
"""

import sqlite3
from typing import Optional

from langchain_core.tools import tool

from config import DB_PATH

SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS exercises (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        primary_muscle TEXT NOT NULL,
        movement_type TEXT NOT NULL,
        equipment TEXT,
        difficulty TEXT,
        contraindications TEXT
    )
"""


def get_db_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    """Idempotent — creates the exercises table if it doesn't exist yet.
    Does NOT seed data; run database/seed.py for that."""
    conn = get_db_connection()
    conn.execute(SCHEMA_SQL)
    conn.commit()
    conn.close()


init_db()


@tool
def search_exercise_db(
    muscle_group: str,
    movement_type: str = "all",
    exclude_contraindication: Optional[str] = None,
) -> str:
    """
    Query the exercise database for exercises matching a muscle group.
    movement_type: compound | isolation | unilateral | all
    exclude_contraindication: body part to avoid (e.g. 'knee_pain')
    """
    conn = get_db_connection()
    query = "SELECT name, equipment, difficulty, movement_type, contraindications FROM exercises WHERE primary_muscle = ?"
    params = [muscle_group]
    if movement_type != "all":
        query += " AND movement_type = ?"
        params.append(movement_type)
    rows = conn.execute(query, params).fetchall()
    conn.close()

    if exclude_contraindication:
        rows = [r for r in rows if not (r[4] and exclude_contraindication in r[4])]

    if not rows:
        return f"No exercises found for [{muscle_group}] [{movement_type}]"

    lines = [f"  • {r[0]} ({r[1] or '?'}, {r[2] or '?'}, {r[3] or '?'})" for r in rows]
    return f"DB results — muscle: [{muscle_group}] | type: [{movement_type}]\n" + "\n".join(lines)
