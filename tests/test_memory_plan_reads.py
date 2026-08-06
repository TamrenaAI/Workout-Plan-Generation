"""
Tests for tools.memory.read_full_plan and read_all_exercise_adjustments —
the two reads GET /sessions/{id}/plan needs to build structured, swap-aware
plan JSON: the whole plan.md (parse_weekly_schedule needs the DAY MAP that
lives outside what read_weekly_schedule already returns), and every
adjustment ever recorded for a session (unlike read_exercise_adjustments,
which is scoped to one day_label/one invocation's `since` window).
"""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import SESSION_DIR
from tools.dynamo import get_plan_adjustments_table
from tools.memory import read_all_exercise_adjustments, read_full_plan


def _make_session(content: str) -> str:
    session_id = str(uuid.uuid4())
    session_path = os.path.join(SESSION_DIR, session_id)
    os.makedirs(session_path, exist_ok=True)
    with open(os.path.join(session_path, "plan.md"), "w", encoding="utf-8") as f:
        f.write(content)
    return session_id


def test_read_full_plan_returns_whole_file_content():
    session_id = _make_session("## Day Map\nDay 1 ...\n\n## Weekly Schedule\n### Day 1\ncontent")
    content = read_full_plan(session_id)
    assert content is not None
    assert "## Day Map" in content
    assert "## Weekly Schedule" in content


def test_read_full_plan_returns_none_when_missing():
    assert read_full_plan(str(uuid.uuid4())) is None


def test_read_all_exercise_adjustments_returns_every_recorded_entry_oldest_first():
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    table = get_plan_adjustments_table()
    table.put_item(Item={
        "adjustment_id": str(uuid.uuid4()),
        "session_day_key": f"{session_id}#Day 1",
        "session_id": session_id, "day_label": "Day 1", "exercise_name": "Barbell Squat",
        "new_exercise_name": "Leg Press", "sets": None, "reps": None, "rpe": None,
        "reason": "Knee pain reported", "created_at": (now - timedelta(minutes=5)).isoformat(),
    })
    table.put_item(Item={
        "adjustment_id": str(uuid.uuid4()),
        "session_day_key": f"{session_id}#Day 2",
        "session_id": session_id, "day_label": "Day 2", "exercise_name": "Bench Press",
        "new_exercise_name": None, "sets": 3, "reps": "10", "rpe": 7,
        "reason": "Too easy, reduced sets", "created_at": now.isoformat(),
    })
    adjustments = read_all_exercise_adjustments(session_id)
    assert len(adjustments) == 2
    assert adjustments[0]["exercise_name"] == "Barbell Squat"
    assert adjustments[0]["new_exercise_name"] == "Leg Press"
    assert adjustments[0]["reason"] == "Knee pain reported"
    assert adjustments[1]["exercise_name"] == "Bench Press"


def test_read_all_exercise_adjustments_returns_empty_list_when_none_recorded():
    assert read_all_exercise_adjustments(str(uuid.uuid4())) == []


def test_read_all_exercise_adjustments_is_scoped_to_session_id():
    session_a = str(uuid.uuid4())
    session_b = str(uuid.uuid4())
    get_plan_adjustments_table().put_item(Item={
        "adjustment_id": str(uuid.uuid4()),
        "session_day_key": f"{session_a}#Day 1",
        "session_id": session_a, "day_label": "Day 1", "exercise_name": "Squat",
        "new_exercise_name": "Leg Press", "sets": None, "reps": None, "rpe": None,
        "reason": "pain", "created_at": datetime.now(timezone.utc).isoformat(),
    })
    assert read_all_exercise_adjustments(session_b) == []
    assert len(read_all_exercise_adjustments(session_a)) == 1
