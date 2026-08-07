"""
Tests for pipeline/monthly_progress.py — deterministic aggregation of a
month's corrective_results (CV rep-tracking, external repo), workout_feedback,
and paired InBody scans into the structured summary consumed by
agents/progress_analyst.py, plus the progress_reports read/write pair.

corrective_results, workout_feedback, inbody_scans, plan_sessions, and
progress_reports all live in DynamoDB (moto'd per-test — see
tests/conftest.py's dynamo_tables fixture).
"""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import ownership
from pipeline import monthly_progress, workout_feedback
from pipeline.inbody_history import record_scan
from tools.inbody import InBodyFlags, InBodyRawExtraction, InBodyResult, SegmentalReading
from tools.dynamo import get_corrective_results_table, get_plan_sessions_table


def _uid() -> str:
    return str(uuid.uuid4())


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


def _insert_corrective_result(session_id, user_id, exercise_name, good, bad, score=85.0, common_errors=None):
    total = good + bad
    get_corrective_results_table().put_item(Item={
        "result_id": str(uuid.uuid4()),
        "user_id": user_id,
        "session_id": session_id,
        "exercise_name": exercise_name,
        "total_reps": total,
        "good_reps": good,
        "bad_reps": bad,
        "accuracy": Decimal(str((good / total * 100) if total else 0.0)),
        "score": Decimal(str(score)),
        "common_errors": common_errors or {},
        "average_rep_duration": Decimal("3.0"),
        "fastest_rep": Decimal("2.5"),
        "slowest_rep": Decimal("4.0"),
        "total_workout_duration": Decimal(str(total * 3.0)),
        "most_common_error": next(iter(common_errors), None) if common_errors else None,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "received_at": datetime.now(timezone.utc).isoformat(),
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
    # Unequal per-submission totals to ensure ratio-of-sums and average-of-averages diverge.
    # Squat 1: 100 total reps, 10 good, 90 bad (10% accuracy, but heavy weight in ratio-of-sums)
    _insert_corrective_result(old_session_id, user_id, "Squat", good=10, bad=90, score=50.0, common_errors={"knee_valgus": 2})
    # Squat 2: 10 total reps, 9 good, 1 bad (90% accuracy, but light weight in ratio-of-sums)
    _insert_corrective_result(old_session_id, user_id, "Squat", good=9, bad=1, score=95.0, common_errors={"knee_valgus": 1})
    # Bench Press: 10 total reps, 10 good, 0 bad (100% accuracy, light weight in ratio-of-sums)
    _insert_corrective_result(old_session_id, user_id, "Bench Press", good=10, bad=0, score=90.0)

    summary = monthly_progress.build_monthly_summary(
        old_session_id=old_session_id, new_session_id="new-2", days_per_week=3, old_created_at=_month_ago(),
    )
    rq = summary["rep_quality"]
    # Overall: (10+9+10) / (100+10+10) = 29/120 = 0.24166...
    # (If wrongly averaged per-submission accuracies: (0.10 + 0.90 + 1.00) / 3 = 2.00/3 = 0.6666... — diverges!)
    assert rq["total_reps"] == 120
    assert rq["good_reps"] == 29
    assert rq["bad_reps"] == 91
    assert rq["accuracy"] == pytest.approx(29 / 120)
    assert rq["avg_score"] == pytest.approx((50.0 + 95.0 + 90.0) / 3)
    # Per-exercise Squat: (10+9) / (100+10) = 19/110 = 0.17272...
    # (If wrongly averaged per-submission accuracies: (0.10 + 0.90) / 2 = 1.00/2 = 0.50 — diverges!)
    assert rq["per_exercise"]["Squat"] == {
        "good": 19, "bad": 91, "accuracy": pytest.approx(19 / 110), "avg_score": pytest.approx((50.0 + 95.0) / 2),
    }
    assert rq["top_form_errors"][0] == {"error_type": "knee_valgus", "count": 3}


def test_rep_quality_empty_when_no_corrective_results():
    summary = monthly_progress.build_monthly_summary(
        old_session_id="old-3", new_session_id="new-3", days_per_week=3, old_created_at=_month_ago(),
    )
    rq = summary["rep_quality"]
    assert rq == {"total_reps": 0, "good_reps": 0, "bad_reps": 0, "accuracy": None, "avg_score": None,
                  "per_exercise": {}, "top_form_errors": []}


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


def test_record_progress_report_is_unique_per_new_session_id():
    """Regression test: the old Mongo index enforced one report per
    new_session_id (db.progress_reports.create_index("new_session_id",
    unique=True)). The DynamoDB table's primary key is now new_session_id
    itself (see pipeline/monthly_progress.py::record_progress_report), so a
    retried/double-submitted monthly review overwrites the same item
    instead of creating a second, non-deterministically-returned report."""
    user_id = _uid()
    monthly_progress.record_progress_report(user_id, "old-dup", "new-dup", {"a": 1}, "First narrative.")
    monthly_progress.record_progress_report(user_id, "old-dup", "new-dup", {"a": 2}, "Second narrative (retry).")

    report = monthly_progress.get_progress_report("new-dup")
    assert report is not None
    assert report["narrative"] == "Second narrative (retry)."
    assert report["summary"] == {"a": 2}

    # Only one item should exist for this new_session_id — a Scan confirms
    # there's no leftover first item under a different report_id.
    from tools.dynamo import get_progress_reports_table
    items = get_progress_reports_table().scan()["Items"]
    matching = [i for i in items if i["new_session_id"] == "new-dup"]
    assert len(matching) == 1


# --- end-to-end regression: get_session's created_at flowing into build_monthly_summary ---

def test_build_monthly_summary_accepts_get_session_created_at():
    # Regression test for the naive/aware datetime bug: api/routes/plan.py's
    # monthly_review handler passes ownership.get_session(...)["created_at"]
    # straight into build_monthly_summary's old_created_at, which subtracts
    # it from an aware datetime.now(timezone.utc) inside _adherence. This
    # exercises that real path (not a pre-built aware datetime) end to end.
    owner_id = _uid()
    old_session_id = "old-real-flow"
    ownership.create_session(old_session_id, owner_id, "hypertrophy")
    # plan_sessions now lives in DynamoDB (see auth/ownership.py), not Mongo.
    get_plan_sessions_table().update_item(
        Key={"session_id": old_session_id},
        UpdateExpression="SET created_at = :created_at",
        ExpressionAttributeValues={
            ":created_at": (datetime.now(timezone.utc) - timedelta(days=28)).isoformat(),
        },
    )

    old_session = ownership.get_session(old_session_id)

    summary = monthly_progress.build_monthly_summary(
        old_session_id=old_session_id,
        new_session_id="new-real-flow",
        days_per_week=3,
        old_created_at=old_session["created_at"],
    )
    rate = summary["adherence"]["adherence_rate"]
    assert isinstance(rate, (int, float))


def test_build_monthly_summary_accepts_get_session_intake_days_per_week():
    """Regression test for the Decimal-leak bug: intake is stored verbatim by
    auth/ownership.create_session and boto3 always deserializes DynamoDB's
    Number type as Decimal, including nested inside the `intake` map. Before
    auth/ownership.py's _serialize converted intake back to native types,
    `days_per_week` read back here would be a Decimal, and _adherence's
    `days_per_week * weeks_elapsed` (weeks_elapsed is a float) raised
    TypeError: unsupported operand type(s) for *: 'decimal.Decimal' and
    'float'. This test goes through the real create_session -> get_session
    round trip (not a hand-built Decimal) and then straight into
    build_monthly_summary, exactly like api/routes/plan.py's same_goal=true
    monthly-review path does."""
    owner_id = _uid()
    old_session_id = "old-decimal-flow"
    ownership.create_session(
        old_session_id, owner_id, "hypertrophy",
        intake={"days_per_week": 3, "age": 30, "experience": "beginner"},
    )
    get_plan_sessions_table().update_item(
        Key={"session_id": old_session_id},
        UpdateExpression="SET created_at = :created_at",
        ExpressionAttributeValues={
            ":created_at": (datetime.now(timezone.utc) - timedelta(days=28)).isoformat(),
        },
    )

    old_session = ownership.get_session(old_session_id)
    days_per_week = old_session["intake"]["days_per_week"]
    assert isinstance(days_per_week, int)  # sanity: this is the round-tripped value

    # Must not raise TypeError — this is the actual crash the reviewer flagged.
    summary = monthly_progress.build_monthly_summary(
        old_session_id=old_session_id,
        new_session_id="new-decimal-flow",
        days_per_week=days_per_week,
        old_created_at=old_session["created_at"],
    )
    # 28 days elapsed -> 4 weeks -> 12 expected sessions at 3/week
    assert summary["adherence"]["sessions_expected"] == 12
