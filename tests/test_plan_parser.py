"""
Tests for pipeline.plan_parser.parse_weekly_schedule — the structured-JSON
counterpart to enforce_volume_budget's rewriting logic, used by
GET /sessions/{id}/plan so the frontend can render the real generated plan
instead of a client-side mock. Fixture content mirrors the real-session
shape already exercised in tests/test_plan_finalize.py (same DAY MAP /
group-section / Weekly Schedule structure), trimmed to what this parser
itself needs to prove.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.plan_parser import parse_weekly_schedule

TWO_DAY_PLAN = """

## User Profile + Plan Header
Goal: hypertrophy
Paradigm: hypertrophy
Days per week: 2
Experience: beginner
Session duration: 45min

Day 1 - hard: muscles [chest, shoulders] | max_sets: 10 | intensity: hard
Day 2 - medium: muscles [back, arms] | max_sets: 10 | intensity: medium

---

## chest - hard
1. Flat Barbell Bench Press 4x8 | Rest 2-3 min | RPE 8
   -> heavy compound pressing.
2. Cable Fly 3x12 | Rest 90s | RPE 7
   -> isolation.

Evidence: compound presses prioritized.

---

## shoulders - hard
1. Seated Dumbbell Overhead Press 3x8 | Rest 2-3 min | RPE 8
   -> compound press.

Evidence: compound press.

---

## back - medium
1. Lat Pulldown 4x10 | Rest 90s | RPE 7
   -> compound pull.

Evidence: compound pull.

---

## arms - medium
1. Barbell Curl 3x10 | Rest 60s | RPE 7
   -> isolation biceps.

Evidence: isolation.

---

## Weekly Schedule
### Day 1 -- Monday: Push (Chest, Shoulders) - Hard Session
**Warm-up:** Dynamic shoulder circles and arm swings.

| # | Exercise | Sets x Reps | Rest | RPE |
|---|----------|-------------|------|-----|
| 1 | Flat Barbell Bench Press | 4x8 | 2-3 min | 8 |
| 2 | Cable Fly | 3x12 | 90s | 7 |
| 3 | Seated Dumbbell Overhead Press | 3x8 | 2-3 min | 8 |

**Coaching notes:** Focus on controlled eccentric phases.

---

### Day 2 -- Tuesday: Pull (Back, Arms) - Medium Session
**Warm-up:** Light rowing and band pull-aparts.

| # | Exercise | Sets x Reps | Rest | RPE |
|---|----------|-------------|------|-----|
| 1 | Lat Pulldown | 4x10 | 90s | 7 |
| 2 | Barbell Curl | 3x10 | 60s | 7 |

**Coaching notes:** Keep elbows pinned on curls.

---

### Weekly Volume Summary
| Muscle Group | Sets/Week | Target | Status |
|---|---|---|---|
| chest | 7 | 10-12 | under |
| shoulders | 3 | 10-12 | under |
| back | 4 | 10-12 | under |
| arms | 3 | 10-12 | under |

### Recovery Notes
- No asymmetry corrections needed.
"""


def test_parses_both_days_in_order():
    days = parse_weekly_schedule(TWO_DAY_PLAN)
    assert [d.day_number for d in days] == [1, 2]
    assert days[0].label == "Day 1 -- Monday: Push (Chest, Shoulders) - Hard Session"
    assert days[1].label == "Day 2 -- Tuesday: Pull (Back, Arms) - Medium Session"


def test_parses_target_focus_from_day_map():
    days = parse_weekly_schedule(TWO_DAY_PLAN)
    assert days[0].target_focus == "CHEST, SHOULDERS"
    assert days[1].target_focus == "BACK, ARMS"


def test_parses_warmup_line():
    days = parse_weekly_schedule(TWO_DAY_PLAN)
    assert days[0].warmup == "Dynamic shoulder circles and arm swings."


def test_parses_exercises_with_sets_reps_rest_rpe():
    days = parse_weekly_schedule(TWO_DAY_PLAN)
    bench = days[0].exercises[0]
    assert bench.name == "Flat Barbell Bench Press"
    assert bench.sets == 4
    assert bench.reps == "8"
    assert bench.rest == "2-3 min"
    assert bench.rpe == "8"


def test_resolves_muscle_group_per_exercise():
    days = parse_weekly_schedule(TWO_DAY_PLAN)
    exercises_by_name = {e.name: e for e in days[0].exercises}
    assert exercises_by_name["Flat Barbell Bench Press"].muscle_group == "chest"
    assert exercises_by_name["Cable Fly"].muscle_group == "chest"
    assert exercises_by_name["Seated Dumbbell Overhead Press"].muscle_group == "shoulders"


def test_new_fields_default_to_none():
    days = parse_weekly_schedule(TWO_DAY_PLAN)
    bench = days[0].exercises[0]
    assert bench.replaced_from is None
    assert bench.adjustment_reason is None


def test_returns_empty_list_when_no_schedule_section():
    assert parse_weekly_schedule("no schedule here, just prose") == []


def test_returns_empty_list_for_empty_content():
    assert parse_weekly_schedule("") == []


def test_malformed_sets_reps_cell_still_parses_row_with_none_sets_reps():
    malformed = TWO_DAY_PLAN.replace("| 1 | Flat Barbell Bench Press | 4x8 | 2-3 min | 8 |",
                                      "| 1 | Flat Barbell Bench Press | n/a | 2-3 min | 8 |")
    days = parse_weekly_schedule(malformed)
    bench = days[0].exercises[0]
    assert bench.name == "Flat Barbell Bench Press"
    assert bench.sets is None
    assert bench.reps is None
    assert bench.rest == "2-3 min"


def test_trailing_plan_adjustment_section_is_not_absorbed_into_last_day():
    """Regression test for a review finding: parse_weekly_schedule only
    stopped the schedule section at '### Weekly Volume Summary' or
    '### Recovery Notes' — but agents/plan_adjuster.py (a separate,
    pre-existing agent) appends a trailing '## Plan Adjustment — {day_label}'
    section to the END of plan.md after every feedback-driven swap. Since
    that '## ' heading wasn't recognized as a terminator, its prose got
    absorbed into the LAST day's block — and if that appended section
    contains a line starting with '|' (plausible prose formatting, e.g. a
    markdown table), it was misparsed as extra/phantom exercise rows on
    that day.
    """
    single_day_plan = """

## User Profile + Plan Header
Day 1 - hard: muscles [chest] | max_sets: 10 | intensity: hard

---

## chest - hard
1. Flat Barbell Bench Press 4x8 | Rest 2-3 min | RPE 8
   -> heavy compound pressing.

Evidence: compound presses prioritized.

---

## Weekly Schedule
### Day 1 -- Monday: Push (Chest) - Hard Session
**Warm-up:** Dynamic shoulder circles.

| # | Exercise | Sets x Reps | Rest | RPE |
|---|----------|-------------|------|-----|
| 1 | Flat Barbell Bench Press | 4x8 | 2-3 min | 8 |

**Coaching notes:** Focus on controlled eccentrics.

## Plan Adjustment — Day 1 -- Monday: Push (Chest) - Hard Session
Swapped Cable Fly -> Machine Chest Press due to reported shoulder pain.

| 1 | Phantom Row | 99x99 | 0s | 0 |
"""
    days = parse_weekly_schedule(single_day_plan)
    assert len(days) == 1
    assert [e.name for e in days[0].exercises] == ["Flat Barbell Bench Press"]
