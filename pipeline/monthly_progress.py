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

from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId

from tools.mongo import get_db


def _adherence(old_session_id: str, days_per_week: int, old_created_at: datetime) -> dict:
    submitted = get_db().workout_feedback.count_documents({"session_id": old_session_id})
    weeks_elapsed = max((datetime.now(timezone.utc) - old_created_at).days / 7, 1e-9)
    expected = round(days_per_week * weeks_elapsed)
    rate = round(min(submitted / expected, 1.0), 3) if expected > 0 else None
    return {"sessions_submitted": submitted, "sessions_expected": expected, "adherence_rate": rate}


def _rep_quality(old_session_id: str) -> dict:
    docs = list(get_db().corrective_results.find({"session_id": old_session_id}))
    if not docs:
        return {"total_reps": 0, "correct_reps": 0, "incorrect_reps": 0, "accuracy": None,
                "per_exercise": {}, "top_form_errors": []}

    total_correct = sum(d["reps_correct"] for d in docs)
    total_incorrect = sum(d["reps_incorrect"] for d in docs)
    total = total_correct + total_incorrect

    per_exercise: dict[str, dict] = {}
    error_counts: dict[str, int] = {}
    for d in docs:
        ex = per_exercise.setdefault(d["exercise_name"], {"correct": 0, "incorrect": 0})
        ex["correct"] += d["reps_correct"]
        ex["incorrect"] += d["reps_incorrect"]
        for fe in d.get("form_errors", []):
            error_counts[fe["error_type"]] = error_counts.get(fe["error_type"], 0) + 1

    for ex in per_exercise.values():
        ex_total = ex["correct"] + ex["incorrect"]
        ex["accuracy"] = ex["correct"] / ex_total if ex_total else None

    top_errors = sorted(error_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]

    return {
        "total_reps": total,
        "correct_reps": total_correct,
        "incorrect_reps": total_incorrect,
        "accuracy": total_correct / total if total else None,
        "per_exercise": per_exercise,
        "top_form_errors": [{"error_type": t, "count": c} for t, c in top_errors],
    }


def _subjective_flags(old_session_id: str) -> dict:
    docs = list(get_db().workout_feedback.find({"session_id": old_session_id}))
    counts: dict[str, dict] = {}
    for d in docs:
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
    old_doc = get_db().inbody_scans.find_one({"session_id": old_session_id})
    new_doc = get_db().inbody_scans.find_one({"session_id": new_session_id})
    if not old_doc or not new_doc:
        return None
    return {
        "skeletal_muscle_mass_kg": round(new_doc["skeletal_muscle_mass_kg"] - old_doc["skeletal_muscle_mass_kg"], 2),
        "body_fat_percent": round(new_doc["body_fat_percent"] - old_doc["body_fat_percent"], 2),
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


def record_progress_report(user_id: str, old_session_id: str, new_session_id: str, summary: dict, narrative: str) -> None:
    get_db().progress_reports.insert_one({
        "user_id": ObjectId(user_id),
        "old_session_id": old_session_id,
        "new_session_id": new_session_id,
        "summary": summary,
        "narrative": narrative,
        "created_at": datetime.now(timezone.utc),
    })


def get_progress_report(new_session_id: str) -> Optional[dict]:
    doc = get_db().progress_reports.find_one({"new_session_id": new_session_id})
    if not doc:
        return None
    return {
        "old_session_id": doc["old_session_id"],
        "new_session_id": doc["new_session_id"],
        "summary": doc["summary"],
        "narrative": doc["narrative"],
        "created_at": doc["created_at"],
    }
