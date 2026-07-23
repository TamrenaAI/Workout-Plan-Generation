"""
InBody scan history — records every scan a user runs through the pipeline
(MongoDB `inbody_scans` collection, same database as everything else) and
compares the two most recent scans. Not agent-invoked: the API route
records a scan right after the InBody pipeline finishes, and reads
history/comparisons when the Progress tab (or the Supervisor's own prompt,
see api/routes/plan.py's _format_inbody_comparison) asks for them.

Values are normalized to kg before storage so comparisons never have to
worry about a user's two scans being in different units (`to_kg` mirrors
tools/inbody.py's own normalization for the asymmetry flags).
"""

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

from tools.inbody import InBodyResult, to_kg
from tools.mongo import get_db


def record_scan(user_id: str, session_id: Optional[str], result: InBodyResult) -> None:
    r, f = result.raw, result.flags
    smm_kg = to_kg(r.skeletal_muscle_mass, r.smm_unit)

    get_db().inbody_scans.insert_one({
        "user_id": ObjectId(user_id),
        "session_id": session_id,
        "skeletal_muscle_mass_kg": smm_kg,
        "body_fat_percent": r.body_fat_percent,
        "bmr_kcal": r.bmr_kcal,
        "arm_asymmetry": f.arm_asymmetry,
        "arm_diff_grams": f.arm_diff_grams,
        "leg_asymmetry": f.leg_asymmetry,
        "leg_diff_grams": f.leg_diff_grams,
        "elevated_bf": f.elevated_bf,
        "trunk_underdeveloped": f.trunk_underdeveloped,
        "created_at": datetime.now(timezone.utc),
    })


def list_scans_for_user(user_id: str) -> list[dict]:
    """Most recent first. Sorts by created_at with _id as a tiebreaker —
    two scans recorded within the same timestamp resolution would
    otherwise sort in an undefined order (ObjectId encodes creation time
    and is monotonically increasing, so it's a reliable secondary key,
    mirroring the old SQLite version's `ORDER BY created_at DESC, id DESC`)."""
    docs = get_db().inbody_scans.find({"user_id": ObjectId(user_id)}).sort([("created_at", -1), ("_id", -1)])
    return [_serialize(d) for d in docs]


def compare_latest_two(user_id: str) -> Optional[dict]:
    """Returns None if the user has fewer than 2 scans — nothing to compare
    yet. Otherwise the two most recent scans plus the deltas between them."""
    docs = list(
        get_db().inbody_scans.find({"user_id": ObjectId(user_id)}).sort([("created_at", -1), ("_id", -1)]).limit(2)
    )
    if len(docs) < 2:
        return None

    latest, previous = _serialize(docs[0]), _serialize(docs[1])
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


def _serialize(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "user_id": str(doc["user_id"]),
        "session_id": doc.get("session_id"),
        "skeletal_muscle_mass_kg": doc["skeletal_muscle_mass_kg"],
        "body_fat_percent": doc["body_fat_percent"],
        "bmr_kcal": doc.get("bmr_kcal"),
        "arm_asymmetry": doc["arm_asymmetry"],
        "arm_diff_grams": doc["arm_diff_grams"],
        "leg_asymmetry": doc["leg_asymmetry"],
        "leg_diff_grams": doc["leg_diff_grams"],
        "elevated_bf": doc["elevated_bf"],
        "trunk_underdeveloped": doc["trunk_underdeveloped"],
        "created_at": doc["created_at"],
    }
