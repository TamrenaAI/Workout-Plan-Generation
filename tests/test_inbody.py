"""
Tests for tools/inbody.py's height extraction — the InBodyRawExtraction
height/height_unit fields, format_inbody_result()'s Height line, and the
to_cm() normalizer.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.inbody import (
    InBodyFlags,
    InBodyRawExtraction,
    InBodyResult,
    SegmentalReading,
    format_inbody_result,
    to_cm,
)


def _make_result(height=None, height_unit=None) -> InBodyResult:
    seg = SegmentalReading(value=3.0, unit="kg", percent_of_ideal=100.0)
    raw = InBodyRawExtraction(
        gender="male",
        weight=80.0,
        weight_unit="kg",
        height=height,
        height_unit=height_unit,
        skeletal_muscle_mass=30.0,
        smm_unit="kg",
        body_fat_percent=20.0,
        bmr_kcal=2000,
        right_arm=seg,
        left_arm=seg,
        trunk=seg,
        right_leg=seg,
        left_leg=seg,
    )
    flags = InBodyFlags(
        arm_asymmetry=False,
        arm_diff_grams=50.0,
        leg_asymmetry=False,
        leg_diff_grams=100.0,
        elevated_bf=False,
        trunk_underdeveloped=False,
    )
    return InBodyResult(raw=raw, flags=flags)


def test_format_inbody_result_includes_height_line_when_present():
    result = _make_result(height=163.0, height_unit="cm")
    text = format_inbody_result(result)
    assert "Height               : 163.0 cm" in text


def test_format_inbody_result_omits_height_line_when_absent():
    result = _make_result(height=None, height_unit=None)
    text = format_inbody_result(result)
    lines = text.splitlines()
    assert not any(line.strip().startswith("Height") for line in lines)
    assert "UNKNOWN" not in text


def test_to_cm_passes_through_cm_unchanged():
    assert to_cm(163.0, "cm") == 163.0


def test_to_cm_converts_feet_inches_five_nine():
    # 5.09 encodes 5'9" (feet.MM, MM = two-digit inch count)
    assert round(to_cm(5.09, "ft_in"), 2) == round(5 * 30.48 + 9 * 2.54, 2)


def test_to_cm_converts_feet_inches_six_feet_even():
    assert round(to_cm(6.00, "ft_in"), 2) == round(6 * 30.48, 2)


def test_to_cm_converts_feet_inches_eleven_inches():
    assert round(to_cm(5.11, "ft_in"), 2) == round(5 * 30.48 + 11 * 2.54, 2)


def test_to_cm_raises_on_unknown_unit():
    with pytest.raises(ValueError):
        to_cm(163.0, "inches")


def test_to_cm_raises_on_out_of_range_ft_in_encoding():
    # 5.90 would decode to 90 "inches" — a VLM outputting the natural 5.9
    # for "5 feet 9 inches" instead of the required 5.09 two-digit form.
    with pytest.raises(ValueError):
        to_cm(5.90, "ft_in")


def test_inbody_raw_extraction_model_dump_includes_height_keys():
    result = _make_result(height=163.0, height_unit="cm")
    dumped = result.raw.model_dump()
    assert dumped["height"] == 163.0
    assert dumped["height_unit"] == "cm"
