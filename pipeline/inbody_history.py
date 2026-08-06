"""
InBody scan history — records every scan a user runs through the pipeline
(DynamoDB `workout_inbody_scans` table) and compares the two most recent
scans. Not agent-invoked: the API route records a scan right after the
InBody pipeline finishes, and reads history/comparisons when the Progress
tab (or the Supervisor's own prompt) asks for them.

Values are normalized to kg before storage so comparisons never have to
worry about a user's two scans being in different units.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from tools.inbody import InBodyResult, to_kg
from tools.dynamo import get_inbody_scans_table


def _dec(value):
    """DynamoDB's Number type has no native float support — boto3 rejects
    plain floats on put_item and always hands back Decimal on read. Convert
    via str() (not Decimal(float)) to avoid binary floating-point noise."""
    return Decimal(str(value)) if isinstance(value, float) else value


def record_scan(user_id: str, session_id: Optional[str], result: InBodyResult) -> None:
    r, f = result.raw, result.flags
    smm_kg = to_kg(r.skeletal_muscle_mass, r.smm_unit)

    item = {
        "scan_id": str(uuid.uuid4()),
        "user_id": user_id,
        "session_id": session_id,
        "skeletal_muscle_mass_kg": _dec(smm_kg),
        "body_fat_percent": _dec(r.body_fat_percent),
        "bmr_kcal": r.bmr_kcal,
        "arm_asymmetry": f.arm_asymmetry,
        "arm_diff_grams": _dec(f.arm_diff_grams),
        "leg_asymmetry": f.leg_asymmetry,
        "leg_diff_grams": _dec(f.leg_diff_grams),
        "elevated_bf": f.elevated_bf,
        "trunk_underdeveloped": f.trunk_underdeveloped,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    get_inbody_scans_table().put_item(Item=item)


def list_scans_for_user(user_id: str) -> list[dict]:
    """Most recent first."""
    resp = get_inbody_scans_table().query(
        IndexName="user-index",
        KeyConditionExpression="user_id = :uid",
        ExpressionAttributeValues={":uid": user_id},
        ScanIndexForward=False,
    )
    docs = sorted(resp["Items"], key=lambda d: (d["created_at"], d["scan_id"]), reverse=True)
    return [_serialize(d) for d in docs]


def compare_latest_two(user_id: str) -> Optional[dict]:
    """Returns None if the user has fewer than 2 scans."""
    resp = get_inbody_scans_table().query(
        IndexName="user-index",
        KeyConditionExpression="user_id = :uid",
        ExpressionAttributeValues={":uid": user_id},
        ScanIndexForward=False,
        Limit=2,
    )
    docs = sorted(resp["Items"], key=lambda d: (d["created_at"], d["scan_id"]), reverse=True)[:2]
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
    bmr = doc.get("bmr_kcal")
    return {
        "id": doc["scan_id"],
        "user_id": doc["user_id"],
        "session_id": doc.get("session_id"),
        "skeletal_muscle_mass_kg": float(doc["skeletal_muscle_mass_kg"]),
        "body_fat_percent": float(doc["body_fat_percent"]),
        "bmr_kcal": int(bmr) if bmr is not None else None,
        "arm_asymmetry": doc["arm_asymmetry"],
        "arm_diff_grams": float(doc["arm_diff_grams"]),
        "leg_asymmetry": doc["leg_asymmetry"],
        "leg_diff_grams": float(doc["leg_diff_grams"]),
        "elevated_bf": doc["elevated_bf"],
        "trunk_underdeveloped": doc["trunk_underdeveloped"],
        "created_at": datetime.fromisoformat(doc["created_at"]),
    }
