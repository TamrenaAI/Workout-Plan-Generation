"""
Regression test for the plan being shown twice ("Weekly Schedule" + "Full
Workout Plan"). Root cause: the Plan Assembler is only ever prompted to write
under the heading "Weekly Schedule" (prompts/plan_assembler.md step 3), but a
real session (sessions/dfd4454f-39e4-479b-a5b3-1152d3beeb47/plan.md) shows it
independently writing a second full copy of the same days under a different
self-chosen heading, "## Full Workout Plan" -- with the Weekly Volume Summary
and Recovery Notes only attached to that second copy.

read_weekly_schedule() used to look only for the literal string
"## Weekly Schedule", so it grabbed from that first heading all the way to
end-of-file -- swallowing the entire duplicate "Full Workout Plan" block in
between. find_last_schedule_marker() now recognizes both headings and picks
whichever occurs LAST, which is the assembler's actual final version.
"""

import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import SESSION_DIR
from pipeline.plan_finalize import enforce_volume_budget
from tools.memory import read_weekly_schedule

# Trimmed down from the real session file: same DAY MAP, same double-write
# under two different headings, same tail only on the second copy.
DOUBLE_WRITE_SESSION = """

## Session Header
Goal: hypertrophy

Day 1 - Upper: muscles [chest, back] | max_sets: 20 | intensity: medium

---

## chest - medium
1. Flat Barbell Bench Press 4x10-12 | Rest 90s | RPE 7
   -> heavy compound pressing movement.
2. Incline Dumbbell Press 3x10-12 | Rest 90s | RPE 7
   -> targets upper chest.

Evidence: compound pressing is foundational.

---

## back - medium
1. Pull-Up 4x10-12 | Rest 90s | RPE 7
   -> foundational vertical pulling compound movement.
2. Barbell Row 4x10-12 | Rest 90s | RPE 7
   -> heavy horizontal pulling compound.

Evidence: pull-ups and rows are foundational.

---

## Weekly Schedule
### Day 1 -- Monday: Upper Body Focus
**Warm-up:** Dynamic shoulder circles.

| # | Exercise | Sets x Reps | Rest | RPE |
|---|----------|-------------|------|-----|
| 1 | Flat Barbell Bench Press | 4x10-12 | 90s | 7 |
| 2 | Pull-Up | 4x10-12 | 90s | 7 |

**Coaching notes:** Prioritize good form.

---

---

## Full Workout Plan
### Day 1 -- Monday: Upper Body Focus
**Warm-up:** Dynamic shoulder circles.

| # | Exercise | Sets x Reps | Rest | RPE |
|---|----------|-------------|------|-----|
| 1 | Flat Barbell Bench Press | 4x10-12 | 90s | 7 |
| 2 | Pull-Up | 4x10-12 | 90s | 7 |

**Coaching notes:** Prioritize good form.

---

### Weekly Volume Summary
| Muscle Group | Sets/Week | Target | Status |
|---|---|---|---|
| chest | 4 | 14-18 | under |
| back | 4 | 14-18 | under |

### Recovery Notes
- No adjustments needed.
"""


def _make_session(content: str) -> str:
    session_id = str(uuid.uuid4())
    session_path = os.path.join(SESSION_DIR, session_id)
    os.makedirs(session_path, exist_ok=True)
    with open(os.path.join(session_path, "plan.md"), "w", encoding="utf-8") as f:
        f.write(content)
    return session_id


def test_read_weekly_schedule_returns_only_the_last_complete_copy():
    session_id = _make_session(DOUBLE_WRITE_SESSION)

    result = read_weekly_schedule(session_id)

    assert result is not None
    assert result.startswith("## Full Workout Plan")
    # Only ONE "Day 1" heading -- the earlier duplicate under "Weekly Schedule"
    # must not be included.
    assert result.count("### Day 1") == 1
    assert "Weekly Volume Summary" in result
    assert "Recovery Notes" in result


def test_enforce_volume_budget_does_not_double_count_days():
    session_id = _make_session(DOUBLE_WRITE_SESSION)

    # Nothing is over budget here (4 sets vs a 20-set budget), so this should
    # find exactly one Day 1 -- not two -- and correctly report no change.
    changed = enforce_volume_budget(session_id)
    assert changed is False
