"""
Regression test for the "chest has 15 exercises" bug: the Plan Assembler
prompt asks the LLM to call validate_session_duration and trim any day over
its max_sets budget itself, but real sessions show this silently not
happening (sessions/c597aeb5-9cac-4f28-adbb-e172cebefa3a/plan.md: Day 1
scheduled 35 sets against a 10-set budget, untouched through two assembler
passes). enforce_volume_budget() re-parses and trims deterministically
instead of trusting the LLM's own edit.

The fixture content below is trimmed down from that real session file (same
DAY MAP, same over-budget Day 1, same malformed-then-fixed table formatting)
to keep the test focused on Day 1 while preserving the exact failure mode.
"""

import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import SESSION_DIR
from pipeline.plan_finalize import enforce_volume_budget
from tools.memory import read_weekly_schedule

REAL_BROKEN_SESSION = """

## User Profile + Plan Header
Goal: hypertrophy
Paradigm: hypertrophy
Days per week: 6
Experience: beginner
Session duration: 45min

Day 1 - hard: muscles [chest, shoulders, arms] | max_sets: 10 | intensity: hard

---

## shoulders - hard
1. Seated Dumbbell Overhead Press 4x8 | Rest 2-3 min | RPE 8
   -> Primary heavy compound movement for overall shoulder development.
2. Cable Lateral Raise 3x12 | Rest 2-3 min | RPE 8
   -> Essential for medial deltoid hypertrophy.
3. Dumbbell Lateral Raise 3x12 | Rest 2-3 min | RPE 8
   -> Additional lateral raise volume.

Evidence: overhead press primary; lateral raises for medial deltoid.

---

## arms - hard
1. Close-Grip Bench Press 4x8 | Rest 2-3 min | RPE 8
   -> heavy compound triceps focus.
2. Barbell Curl 3x8 | Rest 2-3 min | RPE 8
   -> heavy compound biceps loading.
3. Incline Dumbbell Curl 3x8 | Rest 2-3 min | RPE 8
   -> stretches long head of biceps.

Evidence: close-grip bench press and barbell curl are key heavy compounds.

---

## chest - hard
1. Flat Barbell Bench Press 5x8 | Rest 2-3 min | RPE 8
   -> heavy compound pressing for maximal chest recruitment.
2. Incline Dumbbell Press 4x8 | Rest 2-3 min | RPE 8
   -> targets upper chest.
3. Cable Fly 3x12 | Rest 90s | RPE 7
   -> isolation movement for constant tension.
4. Pec Deck 3x12 | Rest 90s | RPE 7
   -> machine isolation.

Evidence: compound presses prioritized; cable flyes and pec deck for isolation.

---

## Weekly Schedule
### Day 1 -- Monday: Push (Chest, Shoulders, Arms) - Hard Session
**Warm-up:** Dynamic shoulder circles and arm swings.

| # | Exercise | Sets x Reps | Rest | RPE |
|---|----------|-------------|------|-----|
| 1 | Flat Barbell Bench Press | 5x8 | 2-3 min | 8 |
| 2 | Incline Dumbbell Press | 4x8 | 2-3 min | 8 |
| 3 | Cable Fly | 3x12 | 90s | 7 |
| 4 | Pec Deck | 3x12 | 90s | 7 |
| 5 | Seated Dumbbell Overhead Press | 4x8 | 2-3 min | 8 |
| 6 | Cable Lateral Raise | 3x12 | 2-3 min | 8 |
| 7 | Dumbbell Lateral Raise | 3x12 | 2-3 min | 8 |
| 8 | Close-Grip Bench Press | 4x8 | 2-3 min | 8 |
| 9 | Barbell Curl | 3x8 | 2-3 min | 8 |
| 10 | Incline Dumbbell Curl | 3x8 | 2-3 min | 8 |

**Coaching notes:** Focus on controlled eccentric phases.

---

### Weekly Volume Summary
| Muscle Group | Sets/Week | Target | Status |
|---|---|---|---|
| chest | 24 | 10-12 | over |
| shoulders | 20 | 10-12 | over |
| arms | 28 | 10-12 | over |

### Recovery Notes
- No asymmetry corrections needed.
"""


def _make_session(content: str) -> str:
    session_id = str(uuid.uuid4())
    session_path = os.path.join(SESSION_DIR, session_id)
    os.makedirs(session_path, exist_ok=True)
    with open(os.path.join(session_path, "plan.md"), "w", encoding="utf-8") as f:
        f.write(content)
    return session_id


def test_returns_false_when_plan_file_missing():
    assert enforce_volume_budget(str(uuid.uuid4())) is False


def test_trims_over_budget_day_and_keeps_primary_exercises():
    session_id = _make_session(REAL_BROKEN_SESSION)

    changed = enforce_volume_budget(session_id)
    assert changed is True

    corrected = read_weekly_schedule(session_id)
    assert corrected is not None

    day1 = corrected.split("### Weekly Volume Summary")[0]

    # Each muscle group's #1 (primary compound) exercise must survive.
    assert "Flat Barbell Bench Press" in day1
    assert "Seated Dumbbell Overhead Press" in day1
    assert "Close-Grip Bench Press" in day1

    # Trimmed all the way down to just the 3 protected primaries (5+4+4=13 sets) --
    # still over the 10-set budget, but that's expected: plan_assembler.md's rule
    # is "never remove the primary compound lift", even if the budget can't be
    # hit exactly as a result. What matters is it dropped from 35 to 13, and only
    # non-primary rows were the ones removed.
    import re
    sets_cells = re.findall(r"\|\s*\d+\s*[×xX]\s*\d+", day1)
    total = sum(int(re.match(r"\|\s*(\d+)", c).group(1)) for c in sets_cells)
    assert total == 13
    assert len(sets_cells) == 3


def test_no_change_when_already_within_budget():
    within_budget = REAL_BROKEN_SESSION.replace(
        """| 1 | Flat Barbell Bench Press | 5x8 | 2-3 min | 8 |
| 2 | Incline Dumbbell Press | 4x8 | 2-3 min | 8 |
| 3 | Cable Fly | 3x12 | 90s | 7 |
| 4 | Pec Deck | 3x12 | 90s | 7 |
| 5 | Seated Dumbbell Overhead Press | 4x8 | 2-3 min | 8 |
| 6 | Cable Lateral Raise | 3x12 | 2-3 min | 8 |
| 7 | Dumbbell Lateral Raise | 3x12 | 2-3 min | 8 |
| 8 | Close-Grip Bench Press | 4x8 | 2-3 min | 8 |
| 9 | Barbell Curl | 3x8 | 2-3 min | 8 |
| 10 | Incline Dumbbell Curl | 3x8 | 2-3 min | 8 |""",
        """| 1 | Flat Barbell Bench Press | 4x8 | 2-3 min | 8 |
| 2 | Seated Dumbbell Overhead Press | 3x8 | 2-3 min | 8 |
| 3 | Close-Grip Bench Press | 3x8 | 2-3 min | 8 |""",
    )
    session_id = _make_session(within_budget)
    assert enforce_volume_budget(session_id) is False
