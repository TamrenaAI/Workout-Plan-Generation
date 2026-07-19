"""
InBody scan history — records every scan a user runs through the pipeline
(SQLite, same database as everything else) and compares the two most
recent scans. Not agent-invoked: the API route records a scan right after
the InBody pipeline finishes, and reads history/comparisons when the
Progress tab asks for them — see docs/CODE_MAP.md's tools/ vs pipeline/
rule.

Values are normalized to kg before storage so comparisons never have to
worry about a user's two scans being in different units (`to_kg` mirrors
tools/inbody.py's own normalization for the asymmetry flags).
"""

import sqlite3
from typing import Optional

from config import DB_PATH
from tools.inbody import InBodyResult, to_kg

SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS inbody_scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        session_id TEXT,
        skeletal_muscle_mass_kg REAL NOT NULL,
        body_fat_percent REAL NOT NULL,
        bmr_kcal INTEGER,
        arm_asymmetry INTEGER NOT NULL,
        arm_diff_grams REAL NOT NULL,
        leg_asymmetry INTEGER NOT NULL,
        leg_diff_grams REAL NOT NULL,
        elevated_bf INTEGER NOT NULL,
        trunk_underdeveloped INTEGER NOT NULL,
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


def record_scan(user_id: int, session_id: Optional[str], result: InBodyResult) -> None:
    r, f = result.raw, result.flags
    smm_kg = to_kg(r.skeletal_muscle_mass, r.smm_unit)

    conn = get_db_connection()
    conn.execute(
        """INSERT INTO inbody_scans
           (user_id, session_id, skeletal_muscle_mass_kg, body_fat_percent, bmr_kcal,
            arm_asymmetry, arm_diff_grams, leg_asymmetry, leg_diff_grams,
            elevated_bf, trunk_underdeveloped)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            user_id, session_id, smm_kg, r.body_fat_percent, r.bmr_kcal,
            int(f.arm_asymmetry), f.arm_diff_grams, int(f.leg_asymmetry), f.leg_diff_grams,
            int(f.elevated_bf), int(f.trunk_underdeveloped),
        ),
    )
    conn.commit()
    conn.close()


def list_scans_for_user(user_id: int) -> list[dict]:
    """Most recent first."""
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT * FROM inbody_scans WHERE user_id = ? ORDER BY created_at DESC, id DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def compare_latest_two(user_id: int) -> Optional[dict]:
    """Returns None if the user has fewer than 2 scans — nothing to compare
    yet. Otherwise the two most recent scans plus the deltas between them."""
    scans = list_scans_for_user(user_id)
    if len(scans) < 2:
        return None

    latest, previous = scans[0], scans[1]
    return {
        "latest": latest,
        "previous": previous,
        "delta": {
            "skeletal_muscle_mass_kg": round(latest["skeletal_muscle_mass_kg"] - previous["skeletal_muscle_mass_kg"], 2),
            "body_fat_percent": round(latest["body_fat_percent"] - previous["body_fat_percent"], 2),
            "arm_asymmetry_resolved": bool(previous["arm_asymmetry"]) and not bool(latest["arm_asymmetry"]),
            "leg_asymmetry_resolved": bool(previous["leg_asymmetry"]) and not bool(latest["leg_asymmetry"]),
            "trunk_underdeveloped_resolved": bool(previous["trunk_underdeveloped"]) and not bool(latest["trunk_underdeveloped"]),
        },
    }
