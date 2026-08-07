"""
Tests for pipeline/inbody_history.py — recording InBody scans per user and
comparing the two most recent ones (the mobile Progress tab's data source,
and the Supervisor's prompt-enrichment source — see api/routes/plan.py's
_format_inbody_comparison).

DynamoDB access is moto-mocked per-test — see tests/conftest.py's
dynamo_tables fixture (autouse).
"""

import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import inbody_history
from tools.inbody import InBodyFlags, InBodyRawExtraction, InBodyResult, SegmentalReading


def _uid() -> str:
    return str(uuid.uuid4())


def _make_result(smm_kg: float, body_fat_percent: float, arm_asymmetry: bool = False) -> InBodyResult:
    seg = SegmentalReading(value=3.0, unit="kg", percent_of_ideal=100.0)
    raw = InBodyRawExtraction(
        gender="male",
        weight=80.0,
        weight_unit="kg",
        skeletal_muscle_mass=smm_kg,
        smm_unit="kg",
        body_fat_percent=body_fat_percent,
        right_arm=seg,
        left_arm=seg,
        trunk=seg,
        right_leg=seg,
        left_leg=seg,
    )
    flags = InBodyFlags(
        arm_asymmetry=arm_asymmetry,
        arm_diff_grams=250.0 if arm_asymmetry else 50.0,
        leg_asymmetry=False,
        leg_diff_grams=100.0,
        elevated_bf=False,
        trunk_underdeveloped=False,
    )
    return InBodyResult(raw=raw, flags=flags)


def test_no_comparison_with_fewer_than_two_scans():
    user_id = _uid()
    inbody_history.record_scan(user_id=user_id, session_id="s1", result=_make_result(30.0, 20.0))
    assert inbody_history.compare_latest_two(user_id=user_id) is None


def test_comparison_reports_deltas_between_two_most_recent_scans():
    user_id = _uid()
    inbody_history.record_scan(user_id=user_id, session_id="s1", result=_make_result(30.0, 20.0, arm_asymmetry=True))
    inbody_history.record_scan(user_id=user_id, session_id="s2", result=_make_result(31.5, 18.5, arm_asymmetry=False))

    comparison = inbody_history.compare_latest_two(user_id=user_id)
    assert comparison is not None
    assert comparison["delta"]["skeletal_muscle_mass_kg"] == pytest.approx(1.5)
    assert comparison["delta"]["body_fat_percent"] == pytest.approx(-1.5)
    assert comparison["delta"]["arm_asymmetry_resolved"] is True


def test_scans_are_scoped_per_user():
    user1, user2 = _uid(), _uid()
    inbody_history.record_scan(user_id=user1, session_id="s1", result=_make_result(30.0, 20.0))
    inbody_history.record_scan(user_id=user2, session_id="s2", result=_make_result(40.0, 15.0))

    assert len(inbody_history.list_scans_for_user(user_id=user1)) == 1
    assert len(inbody_history.list_scans_for_user(user_id=user2)) == 1
