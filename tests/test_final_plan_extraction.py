"""
Regression test for the bug where the user-facing plan sometimes omits
exercises that ARE present in the session's plan.md.

Root cause: the text shown to the user came from the Supervisor's own
free-text final chat reply (a second LLM re-synthesis of the plan), not
from the deterministic Weekly Schedule the Plan Assembler wrote via
write_plan_memory. `read_weekly_schedule` reads that section directly so
the user always sees exactly what was written to memory.
"""

import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import SESSION_DIR
from tools.memory import read_weekly_schedule

FIRST_SCHEDULE = """## Weekly Schedule
### Day 1 - Monday
| # | Exercise | Sets x Reps | Rest | RPE |
|---|----------|-------------|------|-----|
| 1 | Old Bench Press | 4x8 | 90s | 7 |
"""

LATEST_SCHEDULE = """## Weekly Schedule
### Day 1 - Monday
| # | Exercise | Sets x Reps | Rest | RPE |
|---|----------|-------------|------|-----|
| 1 | Flat Barbell Bench Press | 4x8-12 | 60-120s | 6-8 |
| 2 | Incline Dumbbell Press | 4x8-12 | 60-120s | 6-8 |

### Weekly Volume Summary
| Muscle Group | Sets/Week | Target | Status |
|---|---|---|---|
| chest | 30 | 14-18 | over |
"""


def _make_session(content: str) -> str:
    session_id = str(uuid.uuid4())
    session_path = os.path.join(SESSION_DIR, session_id)
    os.makedirs(session_path, exist_ok=True)
    with open(os.path.join(session_path, "plan.md"), "w", encoding="utf-8") as f:
        f.write(content)
    return session_id


def test_returns_none_when_plan_file_missing():
    assert read_weekly_schedule(str(uuid.uuid4())) is None


def test_returns_none_when_no_schedule_section_written_yet():
    session_id = _make_session("## User Profile\nGoal: hypertrophy\n")
    assert read_weekly_schedule(session_id) is None


def test_returns_last_schedule_section_with_exercises_intact():
    # Simulates a re-dispatch/retry appending a second, corrected schedule
    # after an earlier one — the same duplicate-section pattern observed
    # in real session files.
    content = FIRST_SCHEDULE + "\n---\n\n" + LATEST_SCHEDULE
    session_id = _make_session(content)

    result = read_weekly_schedule(session_id)

    assert result is not None
    assert "Flat Barbell Bench Press" in result
    assert "Incline Dumbbell Press" in result
    assert "Old Bench Press" not in result
