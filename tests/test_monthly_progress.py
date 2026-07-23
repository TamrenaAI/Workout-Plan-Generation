"""
Tests for pipeline/monthly_progress.py — deterministic aggregation of a
month's corrective_results (CV rep-tracking, external repo), workout_feedback,
and paired InBody scans into the structured summary consumed by
agents/progress_analyst.py, plus the progress_reports read/write pair.

Mongo access is mongomock'd per-test — see tests/conftest.py's mongo_db
fixture (autouse).
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
from bson import ObjectId

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import monthly_progress, workout_feedback
from pipeline.inbody_history import record_scan
from tools.inbody import InBodyFlags, InBodyRawExtraction, InBodyResult, SegmentalReading
from tools.mongo import get_db


def _uid() -> str:
    return str(ObjectId())


def _make_inbody_result(smm_kg: float, body_fat_percent: float, arm_asymmetry: bool = False) -> InBodyResult:
    seg = SegmentalReading(value=3.0, unit="kg", percent_of_ideal=100.0)
    raw = InBodyRawExtraction(
        gender="male", weight=80.0, weight_unit="kg",
        skeletal_muscle_mass=smm_kg, smm_unit="kg", body_fat_percent=body_fat_percent,
        right_arm=seg, left_arm=seg, trunk=seg, right_leg=seg, left_leg=seg,
    )
    flags = InBodyFlags(
        arm_asymmetry=arm_asymmetry, arm_diff_grams=250.0 if arm_asymmetry else 50.0,
        leg_asymmetry=False, leg_diff_grams=100.0, elevated_bf=False, trunk_underdeveloped=False,
    )
    return InBodyResult(raw=raw, flags=flags)


def _insert_corrective_result(session_id, user_id, exercise_name, correct, incorrect, error_types=None):
    get_db().corrective_results.insert_one({
        "user_id": ObjectId(user_id),
        "session_id": session_id,
        "exercise_id": None,
        "exercise_name": exercise_name,
        "day_label": "Day 1",
        "set_number": 1,
        "reps_attempted": correct + incorrect,
        "reps_correct": correct,
        "reps_incorrect": incorrect,
        "form_errors": [{"rep_index": i, "error_type": et, "confidence": 0.9} for i, et in enumerate(error_types or [])],
        "recorded_at": datetime.now(timezone.utc),
        "received_at": datetime.now(timezone.utc),
    })


def _month_ago():
    return datetime.now(timezone.utc) - timedelta(days=28)


# --- adherence ---------------------------------------------------------------

def test_adherence_computed_from_workout_feedback_count_vs_expected():
    user_id = _uid()
    old_session_id = "old-1"
    for i in range(6):
        workout_feedback.record_feedback(
            user_id, old_session_id, f"Day {i}", [{"name": "Squat", "difficulty": "just_right", "pain": False}], False,
        )

    summary = monthly_progress.build_monthly_summary(
        old_session_id=old_session_id, new_session_id="new-1", days_per_week=3, old_created_at=_month_ago(),
    )
    # 28 days elapsed -> 4 weeks -> 12 expected sessions at 3/week
    assert summary["adherence"]["sessions_submitted"] == 6
    assert summary["adherence"]["sessions_expected"] == 12
    assert summary["adherence"]["adherence_rate"] == pytest.approx(0.5)


# --- rep quality ---------------------------------------------------------------

def test_rep_quality_aggregates_across_corrective_results():
    user_id = _uid()
    old_session_id = "old-2"
    _insert_corrective_result(old_session_id, user_id, "Squat", correct=8, incorrect=2, error_types=["knee_valgus", "knee_valgus"])
    _insert_corrective_result(old_session_id, user_id, "Squat", correct=7, incorrect=3, error_types=["knee_valgus"])
    _insert_corrective_result(old_session_id, user_id, "Bench Press", correct=10, incorrect=0)

    summary = monthly_progress.build_monthly_summary(
        old_session_id=old_session_id, new_session_id="new-2", days_per_week=3, old_created_at=_month_ago(),
    )
    rq = summary["rep_quality"]
    assert rq["total_reps"] == 30
    assert rq["correct_reps"] == 25
    assert rq["incorrect_reps"] == 5
    assert rq["accuracy"] == pytest.approx(25 / 30)
    assert rq["per_exercise"]["Squat"] == {"correct": 15, "incorrect": 5, "accuracy": pytest.approx(0.75)}
    assert rq["top_form_errors"][0] == {"error_type": "knee_valgus", "count": 3}


def test_rep_quality_empty_when_no_corrective_results():
    summary = monthly_progress.build_monthly_summary(
        old_session_id="old-3", new_session_id="new-3", days_per_week=3, old_created_at=_month_ago(),
    )
    rq = summary["rep_quality"]
    assert rq == {"total_reps": 0, "correct_reps": 0, "incorrect_reps": 0, "accuracy": None, "per_exercise": {}, "top_form_errors": []}


# --- subjective flags ---------------------------------------------------------------

def test_subjective_flags_counted_per_exercise():
    user_id = _uid()
    old_session_id = "old-4"
    workout_feedback.record_feedback(user_id, old_session_id, "Day 1", [
        {"name": "Overhead Press", "difficulty": "too_hard", "pain": False},
        {"name": "Overhead Press", "difficulty": "too_hard", "pain": True},
    ], True)
    workout_feedback.record_feedback(user_id, old_session_id, "Day 2", [
        {"name": "Lateral Raise", "difficulty": "too_easy", "pain": False},
    ], False)

    summary = monthly_progress.build_monthly_summary(
        old_session_id=old_session_id, new_session_id="new-4", days_per_week=3, old_created_at=_month_ago(),
    )
    flags = summary["subjective_flags"]
    assert flags["Overhead Press"] == {"too_hard": 2, "too_easy": 0, "pain": 1}
    assert flags["Lateral Raise"] == {"too_hard": 0, "too_easy": 1, "pain": 0}


# --- InBody delta ---------------------------------------------------------------

def test_inbody_delta_uses_session_specific_scans_not_latest_two():
    user_id = _uid()
    old_session_id, new_session_id = "old-5", "new-5"
    record_scan(user_id, old_session_id, _make_inbody_result(30.0, 20.0, arm_asymmetry=True))
    # An ad hoc scan tied to neither session — must be ignored by the delta.
    record_scan(user_id, "unrelated-session", _make_inbody_result(99.0, 99.0))
    record_scan(user_id, new_session_id, _make_inbody_result(31.5, 18.5, arm_asymmetry=False))

    summary = monthly_progress.build_monthly_summary(
        old_session_id=old_session_id, new_session_id=new_session_id, days_per_week=3, old_created_at=_month_ago(),
    )
    delta = summary["inbody_delta"]
    assert delta["skeletal_muscle_mass_kg"] == pytest.approx(1.5)
    assert delta["body_fat_percent"] == pytest.approx(-1.5)
    assert delta["arm_asymmetry_resolved"] is True


def test_inbody_delta_none_when_either_scan_missing():
    summary = monthly_progress.build_monthly_summary(
        old_session_id="old-6", new_session_id="new-6", days_per_week=3, old_created_at=_month_ago(),
    )
    assert summary["inbody_delta"] is None


# --- progress_reports read/write ---------------------------------------------------------------

def test_record_and_get_progress_report_roundtrip():
    user_id = _uid()
    summary = {"adherence": {"sessions_submitted": 1}}
    monthly_progress.record_progress_report(user_id, "old-7", "new-7", summary, "Great month overall.")

    report = monthly_progress.get_progress_report("new-7")
    assert report is not None
    assert report["old_session_id"] == "old-7"
    assert report["narrative"] == "Great month overall."
    assert report["summary"] == summary


def test_get_progress_report_none_when_not_found():
    assert monthly_progress.get_progress_report("never-reviewed") is None
