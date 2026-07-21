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
import re
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

    # Pass 1 removes all 7 non-primary rows, leaving just the 3 protected
    # primaries at 5+4+4=13 sets -- still over the 10-set budget. Pass 2 (the
    # set-reduction fallback) then reduces set counts on those same 3 rows
    # (never removing them) until the day reaches the budget exactly: 10.
    import re
    sets_cells = re.findall(r"\|\s*\d+\s*[×xX]\s*\d+", day1)
    total = sum(int(re.match(r"\|\s*(\d+)", c).group(1)) for c in sets_cells)
    assert total == 10
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
    ).replace(
        """| chest | 24 | 10-12 | over |
| shoulders | 20 | 10-12 | over |
| arms | 28 | 10-12 | over |""",
        """| chest | 4 | 10-12 | under |
| shoulders | 3 | 10-12 | under |
| arms | 3 | 10-12 | under |""",
    )
    session_id = _make_session(within_budget)
    assert enforce_volume_budget(session_id) is False


def test_extract_sets_handles_clean_x_separator():
    from pipeline.plan_finalize import _extract_sets
    assert _extract_sets("4x12") == 4
    assert _extract_sets("4×12") == 4


def test_extract_sets_handles_stray_separator_byte():
    from pipeline.plan_finalize import _extract_sets
    assert _extract_sets("4\x7f12") == 4


def test_extract_sets_handles_a_different_stray_character():
    from pipeline.plan_finalize import _extract_sets
    assert _extract_sets("4?12") == 4


def test_extract_sets_handles_fully_collapsed_digits():
    from pipeline.plan_finalize import _extract_sets
    assert _extract_sets("58") == 5


def test_extract_sets_returns_none_for_unparseable_cell():
    from pipeline.plan_finalize import _extract_sets
    assert _extract_sets("n/a") is None


def test_extract_sets_reps_returns_both_values():
    from pipeline.plan_finalize import _extract_sets_reps
    assert _extract_sets_reps("4\x7f12") == (4, "12")
    assert _extract_sets_reps("4x8-10") == (4, "8-10")
    assert _extract_sets_reps("n/a") is None


REAL_SESSION_ALL_ORDINAL_ONE = """

## User Profile and Plan Header
Goal: hypertrophy
Paradigm: hypertrophy
Days per week: 3
Experience: beginner
Session duration: 45min
Injuries/limits: knee
Priority focus: chest

Day 1 - medium: muscles [chest, back, shoulders, arms, legs] | max_sets: 14 | intensity: medium

---

## chest - medium
1. Flat Barbell Bench Press 4x12 | Rest 90s | RPE 7
   -> heavy compound pressing.
2. Incline Dumbbell Press 4x12 | Rest 90s | RPE 7
   -> upper chest compound.

Evidence: compound pressing.

---

## back - medium
1. Pull-Up 4x12 | Rest 90s | RPE 7
   -> compound bodyweight pull.
2. Lat Pulldown 4x12 | Rest 90s | RPE 7
   -> compound pull alternative.

Evidence: compound pull.

---

## shoulders - medium
1. Seated Dumbbell Overhead Press 4x12 | Rest 90s | RPE 7
   -> compound press.
2. Dumbbell Lateral Raise 4x12 | Rest 90s | RPE 7
   -> isolation.

Evidence: compound press.

---

## arms - medium
1. Close-Grip Bench Press 4x12 | Rest 90s | RPE 7
   -> compound triceps press.
2. Barbell Curl 4x12 | Rest 90s | RPE 7
   -> isolation biceps.

Evidence: compound press.

---

## legs - medium
1. Leg Press 4x12 | Rest 90s | RPE 7
   -> compound quad press.
2. Hip Thrust 4x12 | Rest 90s | RPE 7
   -> compound glute.

Evidence: compound press.

---

## Weekly Schedule
### Day 1 -- Monday: Full Body Focus
**Warm-up:** Light cardio.

| # | Exercise | Sets \x7f Reps | Rest | RPE |
|---|----------|-------------|------|-----|
| 1 | Flat Barbell Bench Press | 4\x7f12 | 90s | 7 |
| 2 | Pull-Up | 4\x7f12 | 90s | 7 |
| 3 | Seated Dumbbell Overhead Press | 4\x7f12 | 90s | 7 |
| 4 | Close-Grip Bench Press | 4\x7f12 | 90s | 7 |
| 5 | Leg Press | 4\x7f12 | 90s | 7 |

**Coaching notes:** Focus on form.

---

### Weekly Volume Summary
| Muscle Group | Sets/Week | Target | Status |
|---|---|---|---|
| chest | 14 | 10-12 | over |
| back | 14 | 10-12 | over |
| shoulders | 11 | 10-12 | met |
| arms | 11 | 10-12 | met |
| legs | 14 | 10-12 | over |

### Recovery Notes
- No asymmetry corrections needed.
"""


def test_reproduces_real_session_bug_stray_byte_and_all_ordinal_one_day():
    """Directly reproduces the real motivating bug: every Sets x Reps cell
    contains a literal 0x7F byte instead of x (previously made every row
    parse as 0 sets, so enforce_volume_budget did nothing despite the day
    being 6 sets over budget), AND every exercise in the day is its muscle
    group's ordinal-1 pick (so the existing removal-based trim can't remove
    anything -- this is the shape of a Full-Body day with one exercise per
    muscle group). Both must be fixed for the day to end up within budget."""
    session_id = _make_session(REAL_SESSION_ALL_ORDINAL_ONE)

    changed = enforce_volume_budget(session_id)
    assert changed is True

    corrected = read_weekly_schedule(session_id)
    day1 = corrected.split("### Weekly Volume Summary")[0]

    for name in [
        "Flat Barbell Bench Press", "Pull-Up", "Seated Dumbbell Overhead Press",
        "Close-Grip Bench Press", "Leg Press",
    ]:
        assert name in day1

    sets_cells = re.findall(r"\|\s*(\d+)[×xX](\d+)\s*\|", day1)
    assert len(sets_cells) == 5
    total = sum(int(sets) for sets, _reps in sets_cells)
    assert total <= 14
    assert "\x7f" not in corrected


def test_set_reduction_stops_at_floor_when_budget_still_not_reachable():
    """If every exercise reduces down to the 2-set floor and the day is
    STILL over budget, the function must stop there rather than looping
    forever or reducing a set count below the floor."""
    unreachable_budget = REAL_SESSION_ALL_ORDINAL_ONE.replace(
        "Day 1 - medium: muscles [chest, back, shoulders, arms, legs] | max_sets: 14 | intensity: medium",
        "Day 1 - medium: muscles [chest, back, shoulders, arms, legs] | max_sets: 5 | intensity: medium",
    )
    session_id = _make_session(unreachable_budget)

    changed = enforce_volume_budget(session_id)
    assert changed is True

    corrected = read_weekly_schedule(session_id)
    day1 = corrected.split("### Weekly Volume Summary")[0]

    sets_cells = re.findall(r"\|\s*(\d+)[×xX](\d+)\s*\|", day1)
    assert len(sets_cells) == 5
    for sets, _reps in sets_cells:
        assert int(sets) == 2
    total = sum(int(sets) for sets, _reps in sets_cells)
    assert total == 10


STALE_SUMMARY_SESSION = """

## User Profile and Plan Header
Goal: hypertrophy
Paradigm: hypertrophy
Days per week: 1
Experience: beginner
Session duration: 45min

Day 1 - medium: muscles [chest] | max_sets: 14 | intensity: medium

---

## chest - medium
1. Flat Barbell Bench Press 4x12 | Rest 90s | RPE 7
   -> heavy compound pressing.
2. Incline Dumbbell Press 4x12 | Rest 90s | RPE 7
   -> upper chest compound.
3. Cable Fly 3x12 | Rest 90s | RPE 7
   -> isolation.

Evidence: compound + isolation.

---

## Weekly Schedule
### Day 1 -- Monday: Chest Focus
**Warm-up:** Light cardio.

| # | Exercise | Sets × Reps | Rest | RPE |
|---|----------|-------------|------|-----|
| 1 | Flat Barbell Bench Press | 4×12 | 90s | 7 |
| 2 | Cable Fly | 3×12 | 90s | 7 |

**Coaching notes:** Focus on form.

---

### Weekly Volume Summary
| Muscle Group | Sets/Week | Target | Status |
|---|---|---|---|
| chest | 14 | 10-12 | over |

### Recovery Notes
- No asymmetry corrections needed.
"""


def test_corrects_stale_summary_even_when_no_day_needed_trimming():
    """Day 1 is genuinely within its 14-set budget (4+3=7 sets scheduled --
    Incline Dumbbell Press was never used, which is fine), but the Weekly
    Volume Summary claims chest=14/over, which doesn't match the real
    schedule (7 sets, under the 10-12 target). This must get corrected even
    though no day was over budget and nothing needed to be trimmed."""
    session_id = _make_session(STALE_SUMMARY_SESSION)

    changed = enforce_volume_budget(session_id)
    assert changed is True

    corrected = read_weekly_schedule(session_id)
    summary = corrected.split("### Weekly Volume Summary")[1]
    assert "| chest | 7 | 10-12 | under |" in summary

    day1 = corrected.split("## Weekly Schedule")[1].split("### Weekly Volume Summary")[0]
    assert "| 1 | Flat Barbell Bench Press | 4×12 | 90s | 7 |" in day1
    assert "| 2 | Cable Fly | 3×12 | 90s | 7 |" in day1


def test_still_returns_false_when_everything_is_already_correct():
    """If the day is within budget AND the summary already matches
    reality, nothing should be rewritten at all."""
    already_correct = STALE_SUMMARY_SESSION.replace(
        "| chest | 14 | 10-12 | over |",
        "| chest | 7 | 10-12 | under |",
    )
    session_id = _make_session(already_correct)
    assert enforce_volume_budget(session_id) is False
