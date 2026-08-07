"""
Monthly progress aggregation — pure Python, no LLM. Combines corrective_results
(CV rep-tracking, a coworker's separate repo, ingested via
api/routes/corrective.py), workout_feedback, and paired InBody scans for a
completed session into one structured summary. Consumed by
agents/progress_analyst.py for narration only — the LLM never recomputes or
restates these numbers, matching the deterministic-math precedent set by
pipeline/inbody_history.py's delta calculation. Also owns progress_reports:
one document per monthly review (old_session_id, new_session_id, the summary
below, and the agent's narrative).
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from tools.dynamo import (
    get_corrective_results_table,
    get_inbody_scans_table,
    get_progress_reports_table,
    get_workout_feedback_table,
)


def _adherence(old_session_id: str, days_per_week: int, old_created_at: datetime) -> dict:
    resp = get_workout_feedback_table().query(
        IndexName="session-index",
        KeyConditionExpression="session_id = :sid",
        ExpressionAttributeValues={":sid": old_session_id},
        Select="COUNT",
    )
    submitted = resp["Count"]
    weeks_elapsed = max((datetime.now(timezone.utc) - old_created_at).days / 7, 1e-9)
    expected = round(days_per_week * weeks_elapsed)
    rate = round(min(submitted / expected, 1.0), 3) if expected > 0 else None
    return {"sessions_submitted": submitted, "sessions_expected": expected, "adherence_rate": rate}


def _rep_quality(old_session_id: str) -> dict:
    resp = get_corrective_results_table().query(
        IndexName="session-index",
        KeyConditionExpression="session_id = :sid",
        ExpressionAttributeValues={":sid": old_session_id},
    )
    # DynamoDB's Number type always deserializes to Decimal — convert good_reps/
    # bad_reps to int and score to float so downstream arithmetic (sums, ratios,
    # averages) and the returned dict match the plain int/float shapes the
    # Mongo-backed version produced (Decimal arithmetic/JSON-serialization
    # would otherwise leak through or blow up).
    docs = [
        {**d, "good_reps": int(d["good_reps"]), "bad_reps": int(d["bad_reps"]), "score": float(d["score"])}
        for d in resp["Items"]
    ]
    if not docs:
        return {"total_reps": 0, "good_reps": 0, "bad_reps": 0, "accuracy": None,
                "avg_score": None, "per_exercise": {}, "top_form_errors": []}

    total_good = sum(d["good_reps"] for d in docs)
    total_bad = sum(d["bad_reps"] for d in docs)
    total = total_good + total_bad

    per_exercise: dict[str, dict] = {}
    error_counts: dict[str, int] = {}
    scores_by_exercise: dict[str, list[float]] = {}
    for d in docs:
        ex = per_exercise.setdefault(d["exercise_name"], {"good": 0, "bad": 0})
        ex["good"] += d["good_reps"]
        ex["bad"] += d["bad_reps"]
        scores_by_exercise.setdefault(d["exercise_name"], []).append(d["score"])
        for error_type, count in d.get("common_errors", {}).items():
            error_counts[error_type] = error_counts.get(error_type, 0) + int(count)

    for name, ex in per_exercise.items():
        ex_total = ex["good"] + ex["bad"]
        ex["accuracy"] = ex["good"] / ex_total if ex_total else None
        scores = scores_by_exercise[name]
        ex["avg_score"] = sum(scores) / len(scores) if scores else None

    top_errors = sorted(error_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
    all_scores = [d["score"] for d in docs]

    return {
        "total_reps": total,
        "good_reps": total_good,
        "bad_reps": total_bad,
        "accuracy": total_good / total if total else None,
        "avg_score": sum(all_scores) / len(all_scores) if all_scores else None,
        "per_exercise": per_exercise,
        "top_form_errors": [{"error_type": t, "count": c} for t, c in top_errors],
    }


def _subjective_flags(old_session_id: str) -> dict:
    resp = get_workout_feedback_table().query(
        IndexName="session-index",
        KeyConditionExpression="session_id = :sid",
        ExpressionAttributeValues={":sid": old_session_id},
    )
    counts: dict[str, dict] = {}
    for d in resp["Items"]:
        for ex in d.get("exercises", []):
            name = ex.get("name")
            if not name:
                continue
            c = counts.setdefault(name, {"too_hard": 0, "too_easy": 0, "pain": 0})
            if ex.get("difficulty") == "too_hard":
                c["too_hard"] += 1
            elif ex.get("difficulty") == "too_easy":
                c["too_easy"] += 1
            if ex.get("pain"):
                c["pain"] += 1
    return counts


def _inbody_delta(old_session_id: str, new_session_id: str) -> Optional[dict]:
    old_resp = get_inbody_scans_table().query(
        IndexName="session-index",
        KeyConditionExpression="session_id = :sid",
        ExpressionAttributeValues={":sid": old_session_id},
        Limit=1,
    )
    new_resp = get_inbody_scans_table().query(
        IndexName="session-index",
        KeyConditionExpression="session_id = :sid",
        ExpressionAttributeValues={":sid": new_session_id},
        Limit=1,
    )
    if not old_resp["Items"] or not new_resp["Items"]:
        return None
    old_doc, new_doc = old_resp["Items"][0], new_resp["Items"][0]
    # DynamoDB's Number type always deserializes to Decimal — convert back
    # to float so this returns the same numeric type the Mongo-backed
    # version did (and round() below rounds a float, not a Decimal).
    old_smm, new_smm = float(old_doc["skeletal_muscle_mass_kg"]), float(new_doc["skeletal_muscle_mass_kg"])
    old_bf, new_bf = float(old_doc["body_fat_percent"]), float(new_doc["body_fat_percent"])
    return {
        "skeletal_muscle_mass_kg": round(new_smm - old_smm, 2),
        "body_fat_percent": round(new_bf - old_bf, 2),
        "arm_asymmetry_resolved": bool(old_doc["arm_asymmetry"]) and not bool(new_doc["arm_asymmetry"]),
        "leg_asymmetry_resolved": bool(old_doc["leg_asymmetry"]) and not bool(new_doc["leg_asymmetry"]),
        "trunk_underdeveloped_resolved": bool(old_doc["trunk_underdeveloped"]) and not bool(new_doc["trunk_underdeveloped"]),
    }


def build_monthly_summary(old_session_id: str, new_session_id: str, days_per_week: int, old_created_at: datetime) -> dict:
    return {
        "adherence": _adherence(old_session_id, days_per_week, old_created_at),
        "rep_quality": _rep_quality(old_session_id),
        "subjective_flags": _subjective_flags(old_session_id),
        "inbody_delta": _inbody_delta(old_session_id, new_session_id),
    }


def _floats_to_decimal(value):
    """summary is a nested dict/list blob (build_monthly_summary's output)
    with real float fields scattered throughout (adherence_rate, rep_quality's
    accuracy/avg_score, inbody_delta's deltas, ...). boto3 rejects native
    floats anywhere in a put_item Item, including nested — recurse and
    convert via str() (not Decimal(float)) to avoid binary floating-point
    noise, same as the module-level float/Decimal note elsewhere."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _floats_to_decimal(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_floats_to_decimal(v) for v in value]
    return value


def record_progress_report(user_id: str, old_session_id: str, new_session_id: str, summary: dict, narrative: str) -> None:
    # new_session_id is the table's primary key (one report per monthly
    # review, matching the old Mongo unique index on new_session_id) — a
    # retried/double-submitted review overwrites the same item instead of
    # silently creating a second, non-deterministically-returned report.
    # report_id is kept as a separate opaque id since other code/consumers
    # may still expect a stable per-report identifier distinct from the key.
    get_progress_reports_table().put_item(Item={
        "new_session_id": new_session_id,
        "report_id": str(uuid.uuid4()),
        "user_id": user_id,
        "old_session_id": old_session_id,
        "summary": _floats_to_decimal(summary),
        "narrative": narrative,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })


def get_progress_report(new_session_id: str) -> Optional[dict]:
    resp = get_progress_reports_table().get_item(Key={"new_session_id": new_session_id})
    doc = resp.get("Item")
    if not doc:
        return None
    return {
        "old_session_id": doc["old_session_id"],
        "new_session_id": doc["new_session_id"],
        "summary": doc["summary"],
        "narrative": doc["narrative"],
        "created_at": datetime.fromisoformat(doc["created_at"]),
    }
