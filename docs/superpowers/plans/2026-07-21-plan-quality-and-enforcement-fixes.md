# Plan Quality & Enforcement Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix eight confirmed plan-quality issues found by comparing a real generated plan against its own stated parameters — a byte-level parsing bug that lets `enforce_volume_budget()` silently no-op, a stale Weekly Volume Summary, and five prompt-content gaps plus one prompt restructure.

**Architecture:** Two independent tracks. `pipeline/plan_finalize.py` gets a more robust parser, a set-reduction fallback for days that can't be fixed by removing exercises, and a Weekly Volume Summary that's always verified against the real schedule. `prompts/supervisor.md`, `prompts/plan_assembler.md`, and `prompts/exercise_recommender.md` each get targeted rule additions for the six issues that are genuinely judgment calls, not deterministic constraints.

**Tech Stack:** Python (stdlib `re`), pytest — no new dependencies.

## Global Constraints

- Every task's automated tests must pass, AND the full suite (`pytest tests/ -q`) must stay green after every task — this plan modifies existing, already-tested code (`pipeline/plan_finalize.py`) and an existing tested prompt (`prompts/exercise_recommender.md`), so regressions are a real risk, not a hypothetical one.
- `pipeline/plan_finalize.py`'s existing fail-safe contract is preserved exactly: unparseable input at any stage still returns `False` with no write. Never trade this away for the new behavior.
- The real session used to diagnose these issues is `sessions/e1d2d06e-e17d-4eca-a5d6-db380f9ce915` — hypertrophy, beginner, 45min/day, 3 days/week, knee injury, chest priority, desk job, elevated BF% (35.0%), same InBody scan is `samples/inbody4.jfif` (male, 270S — this is the sample image actually used to generate that session; do not confuse it with the female/570 scan in `samples/inbody3.jfif`, which was also tested this session but is not the one this plan's fixes are diagnosed against).
- Prompt edits (Tasks 3-8) are additive — do not remove or restructure any existing rule this plan doesn't explicitly call out. Existing tests (`tests/test_exercise_recommender_prompt.py`'s `test_prompt_instructs_passing_goal_to_search_rag`) must keep passing unchanged.
- `MIN_SETS_FLOOR = 2` (pipeline/plan_finalize.py) is the floor below which no exercise's set count is ever reduced by the new fallback.

---

### Task 1: Parsing robustness + set-reduction fallback (`pipeline/plan_finalize.py`)

**Files:**
- Modify: `pipeline/plan_finalize.py`
- Test: `tests/test_plan_finalize.py` (existing file — append, do not remove the 3 existing tests)

**Interfaces:**
- Produces: `_extract_sets_reps(cell: str) -> tuple[int, str] | None` (new — returns both sets and the raw reps string, e.g. `(4, "12")` or `(4, "8-10")`), `_extract_sets(cell: str) -> int | None` (existing signature preserved, now a thin wrapper over `_extract_sets_reps`), `MIN_SETS_FLOOR = 2` (new module constant). `enforce_volume_budget(session_id: str) -> bool`'s signature and fail-safe contract (unparseable input → `False`, no write) are unchanged — its internal trimming behavior gains the set-reduction fallback described below.

This task fixes two confirmed root causes together, since the second was only discovered while verifying the first against the real session:

1. **Parsing:** the real session's cells contain a literal `0x7F` (DEL) byte where "×" should be (`'4\x7f12'`), which neither existing regex tolerates, so `_extract_sets()` returns `None` for every row and the whole function silently does nothing.
2. **All-ordinal-1 exhaustion:** even with parsing fixed, a day where every exercise is its muscle group's ordinal-1 ("primary compound") pick can't be trimmed at all by the existing removal-only logic, since it never removes ordinal-1 rows. This is exactly the shape of a Full-Body day with one exercise per muscle group — confirmed directly: replacing the stray byte with a clean `x` in a sandboxed copy of the real session and re-running `enforce_volume_budget()` leaves Day 1 completely untouched (still 20 sets against its 14-set budget).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_plan_finalize.py` (keep all existing content above this):

```python
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
```

Add `import re` near the top of `tests/test_plan_finalize.py` if it isn't already imported (check the existing file first — it is not currently imported at module level, only inside the existing `test_trims_over_budget_day_and_keeps_primary_exercises` function; add a module-level `import re` alongside the existing `import os`/`import sys`/`import uuid` so the new top-level test functions above can use it directly).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_plan_finalize.py -v`
Expected: the 3 pre-existing tests PASS unchanged; all new tests FAIL — `ImportError: cannot import name '_extract_sets_reps'` for the ones that reference it directly, and assertion failures (wrong totals, missing normalization) for the two new session-level tests, since `_extract_sets` and the trim loop don't yet handle the stray byte or the reduction fallback.

- [ ] **Step 3: Implement the fix**

Replace lines 35-36 of `pipeline/plan_finalize.py`:

```python
_SETS_X_REPS = re.compile(r"(\d+)\s*[×xX]\s*(\d+(?:-\d+)?)")
_SETS_CONCAT = re.compile(r"^(\d)(\d+(?:-\d+)?)$")  # malformed "58" -> sets=5, reps=8
```

with:

```python
_SETS_X_REPS = re.compile(r"(\d+)\s*[×xX]\s*(\d+(?:-\d+)?)")
_SETS_UNKNOWN_SEP = re.compile(r"^(\d)\D+(\d+(?:-\d+)?)$")  # malformed "4\x7f12" -> sets=4, reps=12
_SETS_CONCAT = re.compile(r"^(\d)(\d+(?:-\d+)?)$")  # malformed "58" -> sets=5, reps=8
```

Add `MIN_SETS_FLOOR = 2` as a new module-level constant right after the `_VOLUME_ROW` regex definition (line 45).

Replace the `_extract_sets` function (lines 81-88):

```python
def _extract_sets(cell: str) -> "int | None":
    match = _SETS_X_REPS.search(cell)
    if match:
        return int(match.group(1))
    match = _SETS_CONCAT.match(cell.strip())
    if match:
        return int(match.group(1))
    return None
```

with:

```python
def _extract_sets_reps(cell: str) -> "tuple[int, str] | None":
    match = _SETS_X_REPS.search(cell)
    if match:
        return int(match.group(1)), match.group(2)
    match = _SETS_UNKNOWN_SEP.match(cell.strip())
    if match:
        return int(match.group(1)), match.group(2)
    match = _SETS_CONCAT.match(cell.strip())
    if match:
        return int(match.group(1)), match.group(2)
    return None


def _extract_sets(cell: str) -> "int | None":
    result = _extract_sets_reps(cell)
    return result[0] if result else None
```

In `enforce_volume_budget`, replace the row-building loop:

```python
        rows = []
        for row_line in data_rows:
            cells = _split_row(row_line)
            if len(cells) < 5:
                continue
            exercise_name = cells[1]
            sets = _extract_sets(cells[2])
            lookup = ordinal_lookup.get(exercise_name.strip().lower())
            ordinal, muscle = lookup if lookup else (None, None)
            rows.append({
                "cells": cells, "sets": sets, "ordinal": ordinal, "muscle": muscle,
            })
```

with:

```python
        rows = []
        for row_line in data_rows:
            cells = _split_row(row_line)
            if len(cells) < 5:
                continue
            exercise_name = cells[1]
            sets_reps = _extract_sets_reps(cells[2])
            sets, reps = sets_reps if sets_reps else (None, None)
            lookup = ordinal_lookup.get(exercise_name.strip().lower())
            ordinal, muscle = lookup if lookup else (None, None)
            rows.append({
                "cells": cells, "sets": sets, "reps": reps, "ordinal": ordinal, "muscle": muscle,
            })
```

Replace the trimming block:

```python
        if total > budget:
            changed = True
            while total > budget:
                candidates = [r for r in rows if r["ordinal"] is not None and r["ordinal"] > 1]
                if not candidates:
                    break
                worst = max(candidates, key=lambda r: (r["ordinal"], r["sets"] or 0))
                rows.remove(worst)
                total -= worst["sets"] or 0
```

with:

```python
        if total > budget:
            changed = True

            # Pass 1: remove whole non-primary exercises (ordinal > 1),
            # worst (lowest-priority, most sets) first.
            while total > budget:
                candidates = [r for r in rows if r["ordinal"] is not None and r["ordinal"] > 1]
                if not candidates:
                    break
                worst = max(candidates, key=lambda r: (r["ordinal"], r["sets"] or 0))
                rows.remove(worst)
                total -= worst["sets"] or 0

            # Pass 2: removal alone wasn't enough, or had nothing eligible to
            # remove (e.g. every exercise in this day is its muscle group's
            # ordinal-1 "primary compound" pick -- the shape of a Full-Body
            # day with one exercise per muscle group). Reduce set counts on
            # the remaining rows instead of removing them, one set at a time
            # from whichever row currently has the most, down to a floor of
            # MIN_SETS_FLOOR per exercise.
            while total > budget:
                reducible = [
                    r for r in rows
                    if r["sets"] is not None and r["reps"] is not None and r["sets"] > MIN_SETS_FLOOR
                ]
                if not reducible:
                    break
                worst = max(reducible, key=lambda r: r["sets"])
                worst["sets"] -= 1
                total -= 1
```

Replace the row-rebuild loop:

```python
        rebuilt_row_lines = []
        for idx, r in enumerate(rows, start=1):
            cells = list(r["cells"])
            cells[0] = str(idx)
            rebuilt_row_lines.append("| " + " | ".join(cells) + " |")
```

with:

```python
        rebuilt_row_lines = []
        for idx, r in enumerate(rows, start=1):
            cells = list(r["cells"])
            cells[0] = str(idx)
            if r["sets"] is not None and r["reps"] is not None:
                cells[2] = f"{r['sets']}×{r['reps']}"
            rebuilt_row_lines.append("| " + " | ".join(cells) + " |")
```

This last change also normalizes any malformed separator back to a clean "×" whenever a day block gets rebuilt at all (including rows that weren't themselves trimmed) — a direct side effect of reconstructing the cell from the now-correctly-parsed sets/reps rather than copying the original (possibly malformed) text verbatim.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_plan_finalize.py -v`
Expected: PASS (9 tests: 3 pre-existing + 6 new)

- [ ] **Step 5: Run the full suite**

Run: `pytest tests/ -q`
Expected: PASS, no regressions (this plan's Global Constraints require this after every task)

- [ ] **Step 6: Commit**

```bash
git add pipeline/plan_finalize.py tests/test_plan_finalize.py
git commit -m "$(cat <<'EOF'
Fix silent volume-budget enforcement failure on malformed separators

_extract_sets() only tolerated a recognized x/X/x separator or zero
characters between sets and reps digits -- a real session had a literal
0x7F byte in every cell instead, which made every row parse as 0 sets and
enforce_volume_budget() silently do nothing despite every day being over
budget. Adds a middle parsing tier for any stray separator character, plus
a set-reduction fallback (never removing exercises) for days where every
exercise is its muscle group's ordinal-1 pick -- the existing removal-only
trim can't touch those at all, which is exactly the shape of a Full-Body
day with one exercise per muscle group.
EOF
)"
```

---

### Task 2: Honest Weekly Volume Summary regardless of day-level trimming (`pipeline/plan_finalize.py`)

**Files:**
- Modify: `pipeline/plan_finalize.py`
- Test: `tests/test_plan_finalize.py` (append)

**Interfaces:**
- Consumes: Task 1's `_extract_sets_reps`, the `rows`/`muscle_week_totals` structures already built inside `enforce_volume_budget`.
- Produces: `enforce_volume_budget`'s return-value contract is unchanged (`bool`), but it now also returns `True` (and rewrites the plan) when the Weekly Volume Summary tail doesn't match the real per-day totals, even if no single day was over its own per-day budget.

**Confirmed root cause:** `enforce_volume_budget()` only reaches the summary-rewrite code at all if a day was found over its per-day budget (the existing `changed` flag). The real session's saved summary showed `chest: 14, back: 14, legs: 14` (over) and `shoulders: 11, arms: 11` (met) when the actual scheduled totals for every muscle group were uniformly 11 — the assembler's own stale count was never verified because, after Task 1's fix, no day individually exceeds budget in a way this checks for... actually because the summary check was never independent of day-level trimming at all.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_plan_finalize.py`:

```python
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

    day1 = corrected.split("### Weekly Schedule")[1].split("### Weekly Volume Summary")[0]
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_plan_finalize.py -v`
Expected: `test_corrects_stale_summary_even_when_no_day_needed_trimming` FAILS (`enforce_volume_budget` returns `False`, since Day 1 is within its 14-set budget and nothing triggers a rewrite yet). `test_still_returns_false_when_everything_is_already_correct` currently PASSES already (existing behavior happens to satisfy it) — that's fine, it's here as a regression guard for the change in this step, not a RED check.

- [ ] **Step 3: Implement the fix**

In `enforce_volume_budget`, rename the `changed` variable to `any_day_trimmed` in its two occurrences before the day loop's closing brace: the initialization `changed = False` (change to `any_day_trimmed = False`) and the assignment `changed = True` inside `if total > budget:` (change to `any_day_trimmed = True`). Its third occurrence — the `if not changed: return False` check right after the day loop — is handled by the larger replacement below, which replaces that check along with everything after it through the end of the function:

```python
    if not changed:
        return False

    rebuilt_tail = []
    for line in tail_lines:
        vol_match = _VOLUME_ROW.match(line.strip())
        if vol_match and muscle_week_totals:
            muscle, _old_sets, target, _old_status = vol_match.groups()
            if muscle in muscle_week_totals:
                new_sets = muscle_week_totals[muscle]
                target_range = _parse_target_range(target)
                if target_range:
                    low, high = target_range
                    status = "under" if new_sets < low else "over" if new_sets > high else "met"
                else:
                    status = _old_status
                rebuilt_tail.append(f"| {muscle} | {new_sets} | {target} | {status} |")
                continue
        rebuilt_tail.append(line)

    body_lines = []
    for day_lines in rebuilt_days:
        body_lines.extend(day_lines)
    body_lines.extend(rebuilt_tail)

    corrected_body = "\n".join(body_lines).strip()
    write_plan_memory.invoke({
        "session_id": session_id,
        "section_title": "Weekly Schedule",
        "content": corrected_body,
    })
    return True
```

with:

```python
    # Always attempt a corrected tail (cheap, no side effects) -- comparing
    # it against the original tells us whether the summary itself needed
    # correcting, independent of whether any day's rows were modified above.
    rebuilt_tail = []
    for line in tail_lines:
        vol_match = _VOLUME_ROW.match(line.strip())
        if vol_match and muscle_week_totals:
            muscle, _old_sets, target, _old_status = vol_match.groups()
            if muscle in muscle_week_totals:
                new_sets = muscle_week_totals[muscle]
                target_range = _parse_target_range(target)
                if target_range:
                    low, high = target_range
                    status = "under" if new_sets < low else "over" if new_sets > high else "met"
                else:
                    status = _old_status
                rebuilt_tail.append(f"| {muscle} | {new_sets} | {target} | {status} |")
                continue
        rebuilt_tail.append(line)

    summary_needs_correction = bool(muscle_week_totals) and rebuilt_tail != tail_lines

    if not any_day_trimmed and not summary_needs_correction:
        return False

    body_lines = []
    for day_lines in rebuilt_days:
        body_lines.extend(day_lines)
    body_lines.extend(rebuilt_tail)

    corrected_body = "\n".join(body_lines).strip()
    write_plan_memory.invoke({
        "session_id": session_id,
        "section_title": "Weekly Schedule",
        "content": corrected_body,
    })
    return True
```

Also update the function's docstring, which by this point describes neither Task 1's reduction fallback nor this task's independent summary-correction trigger. Replace the whole docstring:

```python
def enforce_volume_budget(session_id: str) -> bool:
    """Trims any day of the LAST '## Weekly Schedule' section that exceeds its
    DAY MAP max_sets budget, and recomputes the Weekly Volume Summary from the
    trimmed days. Appends the corrected schedule as a new section if any
    changes were made. Returns True if a correction was written, False if the
    schedule was already within budget (or couldn't be parsed) and nothing
    needed to change."""
```

with:

```python
def enforce_volume_budget(session_id: str) -> bool:
    """Trims any day of the LAST '## Weekly Schedule' section that exceeds its
    DAY MAP max_sets budget -- removing non-primary (ordinal > 1) exercises
    first, then reducing set counts (never removing the row) down to
    MIN_SETS_FLOOR if removal alone can't or couldn't reach the budget, e.g.
    when every exercise in the day is its muscle group's ordinal-1 pick.
    Always recomputes the Weekly Volume Summary from the real per-day
    totals and rewrites it if it doesn't match what's currently written,
    independent of whether any day's rows needed trimming. Appends the
    corrected schedule as a new section if any day's rows were modified OR
    the summary didn't match reality. Returns True if a correction was
    written, False if nothing needed to change (or the schedule couldn't be
    parsed)."""
```

Also replace the module-level docstring at the very top of `pipeline/plan_finalize.py`, which still only describes the original two failure modes (missing separator, LLM not trimming) and not the two this plan added (stray-byte tolerance beyond a simple missing separator, and the ordinal-exhaustion reduction fallback) or Task 2's independent summary-correction trigger:

```python
"""
Deterministic post-processing for the assembled Weekly Schedule.

prompts/plan_assembler.md step 4 asks the LLM to call validate_session_duration
and trim any day over its max_sets budget itself, by rewriting the table. In
practice this doesn't reliably happen:

- The assembler sometimes writes "Sets x Reps" cells without the required
  "x" separator (e.g. "5 8" collapsed to "58"), which silently breaks
  validate_session_duration's regex-based set counting — an over-budget day
  reads as 0 scheduled sets and passes.
- Even when formatted correctly and clearly over budget, the LLM has been
  observed to not actually rewrite the day (see sessions/c597aeb5-...: Day 1
  scheduled 35 sets against a 10-set budget, survived untouched through two
  assembler passes).

enforce_volume_budget() re-parses whatever schedule the assembler actually
wrote, trims any day still over budget using the same priority rule already
documented in plan_assembler.md ("never remove the primary compound lift for
any muscle group"), and appends the corrected schedule as a fresh
'## Weekly Schedule' section. tools.memory.read_weekly_schedule() already
returns the LAST such section, so the corrected version becomes what's shown
to the user with no other wiring changes needed.

Exercises this can't confidently classify (couldn't be matched back to a
muscle group's numbered prescription list) are never auto-removed — being
conservative about what we delete matters more than hitting the budget
exactly.
"""
```

with:

```python
"""
Deterministic post-processing for the assembled Weekly Schedule.

prompts/plan_assembler.md step 4 asks the LLM to call validate_session_duration
and trim any day over its max_sets budget itself, by rewriting the table. In
practice this doesn't reliably happen:

- The assembler sometimes writes "Sets x Reps" cells without the required
  "x" separator, or with a stray unexpected character in its place (a real
  session was found with a literal ASCII DEL byte, 0x7F, where "x" should have
  been) — either of which used to silently break set counting entirely,
  making an over-budget day read as 0 scheduled sets.
- Even when formatted correctly and clearly over budget, the LLM has been
  observed to not actually rewrite the day (see sessions/c597aeb5-...: Day 1
  scheduled 35 sets against a 10-set budget, survived untouched through two
  assembler passes).
- Even when the assembler's per-day removal logic works, a day where every
  exercise is its muscle group's ordinal-1 ("primary compound") pick can't be
  fixed by removing exercises at all, since the priority rule never removes
  an ordinal-1 row — this is exactly the shape of a Full-Body day with one
  exercise per muscle group.
- The assembler's own Weekly Volume Summary can also just be wrong (stale
  relative to whatever the final per-day tables actually say), independent
  of whether any single day was over its own per-day budget.

enforce_volume_budget() re-parses whatever schedule the assembler actually
wrote, trims any day still over budget using the same priority rule already
documented in plan_assembler.md ("never remove the primary compound lift for
any muscle group") — falling back to reducing set counts (never removing the
row) when removal alone can't or couldn't reach the budget — and always
recomputes the Weekly Volume Summary from the real per-day totals, rewriting
it if it doesn't match what's currently written even when no day needed
trimming. Appends the corrected schedule as a fresh '## Weekly Schedule'
section. tools.memory.read_weekly_schedule() already returns the LAST such
section, so the corrected version becomes what's shown to the user with no
other wiring changes needed.

Exercises this can't confidently classify (couldn't be matched back to a
muscle group's numbered prescription list) are never auto-removed or
auto-reduced — being conservative about what we touch matters more than
hitting the budget exactly.
"""
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_plan_finalize.py -v`
Expected: PASS (11 tests: 9 from Task 1 + 2 new)

- [ ] **Step 5: Run the full suite**

Run: `pytest tests/ -q`
Expected: PASS, no regressions

- [ ] **Step 6: Commit**

```bash
git add pipeline/plan_finalize.py tests/test_plan_finalize.py
git commit -m "$(cat <<'EOF'
Always verify the Weekly Volume Summary against the real schedule

enforce_volume_budget() only ever reached the summary-rewrite code when a
day was over its own per-day budget -- a real session's saved summary
showed made-up numbers (14/14/11/11/14) that didn't match the actual
uniform 11-sets-per-muscle schedule, and nothing caught it since no day
was (at the time) detected as over budget. The summary is now always
recomputed and compared against what's currently written, independent of
whether any day's rows needed trimming.
EOF
)"
```

---

### Task 3: Priority-muscle volume boost (`prompts/supervisor.md`)

**Files:**
- Modify: `prompts/supervisor.md`
- Test: `tests/test_supervisor_prompt.py` (new)

**Interfaces:**
- Consumes: `config.load_prompt`
- Produces: nothing new — a prompt-content addition only.

**Confirmed root cause:** `"priority"` appears in the prompt set exactly once, as a de-prioritization tiebreaker during trimming (`plan_assembler.md`: "trim in this order (lowest priority first)"). Nothing translates a stated `Priority focus: {muscle}` into *more* volume for that muscle — every muscle group gets an identical weekly-volume target regardless.

- [ ] **Step 1: Write the failing test**

Create `tests/test_supervisor_prompt.py`:

```python
"""Confirms the supervisor prompt tells the agent to give a stated priority
muscle extra weekly volume -- a plain-text assertion since the prompt is
only ever consumed by an LLM, not by code."""

from config import load_prompt


def test_prompt_instructs_targeting_top_of_range_for_priority_muscle():
    text = load_prompt("supervisor")
    assert "target the TOP of the range" in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_supervisor_prompt.py -v`
Expected: FAIL — assertion error, the phrase isn't in the prompt yet.

- [ ] **Step 3: Edit `prompts/supervisor.md`**

Replace:

```
2. Based on the user's intake form, InBody data, and paradigm, decide:
   - Training split (Full Body / PPL / Upper-Lower / Body Part based on days_per_week + experience)
   - The exact list of muscle_group IDs you will dispatch (see "Muscle group IDs and leg-day
     differentiation" below)
   - Intensity zone per group, using the zone labels for THIS paradigm (see "Paradigm reference
     table" below) - e.g. hard/medium/soft for hypertrophy, heavy/volume/speed for strength
   - Weekly volume per group using this paradigm's volume metric (apply reduction factors below
     only where the paradigm uses a sets/week metric)
```

with:

```
2. Based on the user's intake form, InBody data, and paradigm, decide:
   - Training split (Full Body / PPL / Upper-Lower / Body Part based on days_per_week + experience)
   - The exact list of muscle_group IDs you will dispatch (see "Muscle group IDs and leg-day
     differentiation" below)
   - Intensity zone per group, using the zone labels for THIS paradigm (see "Paradigm reference
     table" below) - e.g. hard/medium/soft for hypertrophy, heavy/volume/speed for strength
   - Weekly volume per group using this paradigm's volume metric (apply reduction factors below
     only where the paradigm uses a sets/week metric). If the intake form's Priority focus names
     this muscle group, target the TOP of the range instead of anywhere else in it (e.g. beginner
     hypertrophy's 10-12 becomes 12, not 10, for the priority muscle specifically) - this applies
     only to the priority muscle; every other group still uses its normal range.
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_supervisor_prompt.py -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `pytest tests/ -q`
Expected: PASS, no regressions

- [ ] **Step 6: Commit**

```bash
git add prompts/supervisor.md tests/test_supervisor_prompt.py
git commit -m "$(cat <<'EOF'
Give a stated priority muscle extra weekly volume, not just tiebreak status

"Priority focus" previously only mattered as a de-prioritization tiebreaker
during trimming (plan_assembler.md) -- nothing translated it into more
volume. The Supervisor now targets the top of the paradigm's volume range
for the priority muscle specifically.
EOF
)"
```

---

### Task 4: Push/pull balance on Full-Body days (`prompts/plan_assembler.md`)

**Files:**
- Modify: `prompts/plan_assembler.md`
- Test: `tests/test_plan_assembler_prompt.py` (new)

**Interfaces:**
- Consumes: `config.load_prompt`
- Produces: nothing new — a prompt-content addition only.

**Confirmed root cause:** movement-pattern-balance guidance exists only for the `general_fitness` paradigm and for *choosing* a Push/Pull/Legs split structure — nothing governs push/pull composition *within* a single Full-Body day (what beginners are put on). The real session's Day 1 had three pressing-pattern lifts (bench, overhead press, close-grip bench) against one pulling lift (pull-up). Confirmed separately: the exercise DB's `movement_type` column only has `compound`/`isolation`/`unilateral` — no push/pull data exists anywhere, so this stays an LLM-judgment rule, not a deterministic check (a `primary_muscle`-based heuristic would misclassify Close-Grip Bench Press, `primary_muscle=arms`, as non-press).

- [ ] **Step 1: Write the failing test**

Create `tests/test_plan_assembler_prompt.py`:

```python
"""Confirms the plan_assembler prompt balances push/pull composition within
a single day, and frames BF%-related notes honestly (see Task 8) -- plain-text
assertions since the prompt is only ever consumed by an LLM, not by code."""

from config import load_prompt


def test_prompt_balances_push_pull_within_a_single_day():
    text = load_prompt("plan_assembler")
    assert "pressing-pattern exercises" in text
    assert "pulling-pattern exercises" in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_plan_assembler_prompt.py -v`
Expected: FAIL — assertion error, the phrases aren't in the prompt yet.

- [ ] **Step 3: Edit `prompts/plan_assembler.md`**

Replace:

```
## Scheduling rules (mandatory)
- NEVER place the same muscle group on consecutive days.
- Place the hardest session (most volume / heaviest loading) where the longest recovery window
  follows it (e.g. before a rest day).
- For Upper/Lower splits: alternate Upper → Lower → Upper → Lower. legs_a and legs_b are two
  DIFFERENT sections in plan memory with different exercises — schedule each on its own Lower
  day using its own content. Do not copy one leg day's exercises onto the other.
- For PPL: Push → Pull → Legs in order, repeat if 6 days.
```

with:

```
## Scheduling rules (mandatory)
- NEVER place the same muscle group on consecutive days.
- Place the hardest session (most volume / heaviest loading) where the longest recovery window
  follows it (e.g. before a rest day).
- For Upper/Lower splits: alternate Upper → Lower → Upper → Lower. legs_a and legs_b are two
  DIFFERENT sections in plan memory with different exercises — schedule each on its own Lower
  day using its own content. Do not copy one leg day's exercises onto the other.
- For PPL: Push → Pull → Legs in order, repeat if 6 days.
- Within any single day (this matters most for Full-Body splits, where it's easy to stack
  presses from different muscle groups' prescriptions without noticing), the count of
  pressing-pattern exercises (bench/overhead press variants, dips, close-grip presses) must not
  exceed the count of pulling-pattern exercises (rows, pull-ups, pulldowns, curls) by more than
  one. If a day ends up imbalanced, swap the lowest-priority press for the best-fitting row/pull
  variant already prescribed for that muscle group in plan memory — never introduce an exercise
  that wasn't already prescribed by the Exercise Recommender.
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_plan_assembler_prompt.py -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `pytest tests/ -q`
Expected: PASS, no regressions

- [ ] **Step 6: Commit**

```bash
git add prompts/plan_assembler.md tests/test_plan_assembler_prompt.py
git commit -m "$(cat <<'EOF'
Balance push/pull composition within a single day

Movement-pattern balance previously only applied to the general_fitness
paradigm and to choosing a PPL split structure -- nothing governed the
push/pull composition within a single Full-Body day, which is exactly the
split beginners are put on. A real session had 3 pressing exercises
against 1 pulling exercise in the same session.
EOF
)"
```

---

### Task 5: Beginner-appropriate exercise/rep selection (`prompts/exercise_recommender.md`)

**Files:**
- Modify: `prompts/exercise_recommender.md`
- Test: `tests/test_exercise_recommender_prompt.py` (existing file — append, keep the existing test)

**Interfaces:**
- Consumes: `config.load_prompt`
- Produces: nothing new — a prompt-content addition only.

**Confirmed root cause:** the real session prescribed Pull-Up at 4×12 for a stated beginner — the zone's numeric prescription gets mechanically applied to whichever exercise was selected, with no check for achievability at the stated experience level and no instruction to prefer a regressed variant for bodyweight-loaded compounds.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_exercise_recommender_prompt.py`:

```python
def test_prompt_prefers_regressed_variants_for_beginners_on_bodyweight_compounds():
    text = load_prompt("exercise_recommender")
    assert "assisted or regressed variant" in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_exercise_recommender_prompt.py -v`
Expected: the existing test PASSES unchanged; the new test FAILS — assertion error.

- [ ] **Step 3: Edit `prompts/exercise_recommender.md`**

Replace:

```
4. Select 3-5 exercises based on RAG guidance and DB results, using the sets/reps/rest/RPE from
   YOUR paradigm's table for your zone label, and (if applicable) your emphasis brief. Confirm the
   total sets across all exercises does NOT exceed your max_sets budget - if it would, drop the
   lowest-priority exercise first.
```

with:

```
4. Select 3-5 exercises based on RAG guidance and DB results, using the sets/reps/rest/RPE from
   YOUR paradigm's table for your zone label, and (if applicable) your emphasis brief. Confirm the
   total sets across all exercises does NOT exceed your max_sets budget - if it would, drop the
   lowest-priority exercise first.

   For beginners specifically: on bodyweight-loaded compounds (pull-ups, dips, and similar), prefer
   an assisted or regressed variant (e.g. lat pulldown or assisted pull-up instead of a strict
   pull-up, bench dip instead of a weighted dip) unless the DB or RAG evidence indicates the exact
   movement is appropriate for this user as prescribed. Cap the rep target at what's realistic for
   whichever variant you actually select - do not apply the zone table's rep number to an exercise
   the stated experience level couldn't realistically perform for that many reps.
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_exercise_recommender_prompt.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full suite**

Run: `pytest tests/ -q`
Expected: PASS, no regressions

- [ ] **Step 6: Commit**

```bash
git add prompts/exercise_recommender.md tests/test_exercise_recommender_prompt.py
git commit -m "$(cat <<'EOF'
Prefer regressed exercise variants and realistic reps for beginners

A real session prescribed Pull-Up 4x12 for a stated beginner -- the zone's
rep/set numbers were mechanically applied with no check for whether the
selected exercise variant is achievable at the stated experience level.
EOF
)"
```

---

### Task 6: Compound/isolation rep-range split (`prompts/exercise_recommender.md`)

**Files:**
- Modify: `prompts/exercise_recommender.md`
- Test: `tests/test_exercise_recommender_prompt.py` (append)

**Interfaces:**
- Consumes: `config.load_prompt`
- Produces: nothing new — a prompt-content restructure only.

**Confirmed root cause:** every one of the 18 exercises prescribed across all 5 muscle groups in the real session is exactly "12" reps — the hypertrophy zone table gives one rep number per zone, full stop, with no axis for exercise role. The `fat_loss` table has the identical structure (one Reps column) and the identical issue. The other five paradigm tables already differentiate by role through other means (strength's main/supplemental/accessory rep windows, athletic_performance's power/strength/conditioning zones, general_fitness/endurance_complement/rehabilitation's explicit de-emphasis of isolation work) and are intentionally left unchanged — restructuring them would contradict guidance they already state correctly.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_exercise_recommender_prompt.py`:

```python
def test_prompt_splits_hypertrophy_reps_by_compound_vs_isolation():
    text = load_prompt("exercise_recommender")
    assert "Compound Reps" in text
    assert "Isolation Reps" in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_exercise_recommender_prompt.py -v`
Expected: the 2 existing tests PASS unchanged; the new test FAILS.

- [ ] **Step 3: Edit `prompts/exercise_recommender.md`**

Replace:

```
### Paradigm: hypertrophy
| Zone   | Sets | Reps  | Rest    | RPE | Focus |
|--------|------|-------|---------|-----|-------|
| hard   | 4-5  | 6-8   | 2-3 min | 8-9 | heavy compound first |
| medium | 3-4  | 10-12 | 90s     | 7   | compound + isolation |
| soft   | 3    | 15+   | 60s     | 5-6 | corrective / unilateral |
```

with:

```
### Paradigm: hypertrophy
| Zone   | Sets | Compound Reps | Isolation Reps | Rest    | RPE | Focus |
|--------|------|----------------|-----------------|---------|-----|-------|
| hard   | 4-5  | 6-8            | 10-12           | 2-3 min | 8-9 | heavy compound first |
| medium | 3-4  | 8-10           | 12-15           | 90s     | 7   | compound + isolation |
| soft   | 3    | 12-15          | 15-20           | 60s     | 5-6 | corrective / unilateral |

Use the Compound Reps column for multi-joint lifts (bench press, squat, row, overhead press,
pull-up, etc.) and the Isolation Reps column for single-joint/machine/cable movements (lateral
raise, curl, pushdown, leg extension, calf raise, etc.) — classify each exercise by the same
compound/isolation distinction already used by search_exercise_db's movement_type field. Never
apply one rep number to every exercise in a session regardless of its role.
```

Replace:

```
### Paradigm: fat_loss
| Zone     | Sets | Reps  | Rest   | RPE | Focus |
|----------|------|-------|--------|-----|-------|
| circuit  | 3-4  | 15-20 | 45s    | 7-8 | density, superset-friendly |
| moderate | 3    | 12-15 | 60-75s | 6-7 | compound movements, full ROM |
| low      | 2-3  | 15+   | 45s    | 5-6 | corrective / finisher |
```

with:

```
### Paradigm: fat_loss
| Zone     | Sets | Compound Reps | Isolation Reps | Rest   | RPE | Focus |
|----------|------|----------------|-----------------|--------|-----|-------|
| circuit  | 3-4  | 12-15          | 15-20           | 45s    | 7-8 | density, superset-friendly |
| moderate | 3    | 10-12          | 12-15           | 60-75s | 6-7 | compound movements, full ROM |
| low      | 2-3  | 12-15          | 15-20           | 45s    | 5-6 | corrective / finisher |

Same Compound/Isolation Reps distinction as the hypertrophy table above.
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_exercise_recommender_prompt.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full suite**

Run: `pytest tests/ -q`
Expected: PASS, no regressions

- [ ] **Step 6: Commit**

```bash
git add prompts/exercise_recommender.md tests/test_exercise_recommender_prompt.py
git commit -m "$(cat <<'EOF'
Split hypertrophy/fat_loss rep ranges by compound vs isolation role

All 18 exercises in a real session were prescribed exactly "12" reps
regardless of role -- the zone tables gave one rep number per zone, full
stop. Only hypertrophy and fat_loss had this exact issue; the other five
paradigms already differentiate by role through other means and are left
unchanged.
EOF
)"
```

---

### Task 7: Injury/limitation guidance substance (`prompts/exercise_recommender.md`)

**Files:**
- Modify: `prompts/exercise_recommender.md`
- Test: `tests/test_exercise_recommender_prompt.py` (append)

**Interfaces:**
- Consumes: `config.load_prompt`
- Produces: nothing new — a prompt-content addition only.

**Confirmed root cause:** the only injury-specific guidance anywhere in the prompt set is gated behind the `rehabilitation` **paradigm** (a full goal reclassification) — there is no rule for "an injury/limitation flag is present" under any *other* paradigm, which is exactly the real session's case (hypertrophy paradigm, knee injury flag). The real output's only guidance was a label ("knee-safe exercises... considerations"), never a concrete cue or fallback.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_exercise_recommender_prompt.py`:

```python
def test_prompt_gives_concrete_injury_guidance_under_any_paradigm():
    text = load_prompt("exercise_recommender")
    assert "Injury/limitation rule" in text
    assert "regardless of paradigm" in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_exercise_recommender_prompt.py -v`
Expected: the 3 existing tests PASS unchanged; the new test FAILS.

- [ ] **Step 3: Edit `prompts/exercise_recommender.md`**

Replace:

```
## Elevated BF% rule (soft hint only - do not treat as a fixed override)
If you were given ELEVATED_BF: prefer the upper end of your zone's rep range (e.g. 8 over 6 for a
hypertrophy "hard" zone, 12 over 10 for "medium") as a general lean, not a fixed rule applied
identically to every exercise - reps should still vary across your exercises based on exercise
type and load. This flag is most relevant for hypertrophy and fat_loss paradigms; for paradigms
whose rep windows are already fixed by injury or protocol (rehabilitation, endurance_complement),
do not let it override the table above.

## Output format for write_plan_memory (section_title = "{your muscle_group ID} - {ZONE LABEL}")
```

with:

```
## Elevated BF% rule (soft hint only - do not treat as a fixed override)
If you were given ELEVATED_BF: prefer the upper end of your zone's rep range (e.g. 8 over 6 for a
hypertrophy "hard" zone, 12 over 10 for "medium") as a general lean, not a fixed rule applied
identically to every exercise - reps should still vary across your exercises based on exercise
type and load. This flag is most relevant for hypertrophy and fat_loss paradigms; for paradigms
whose rep windows are already fixed by injury or protocol (rehabilitation, endurance_complement),
do not let it override the table above.

## Injury/limitation rule (applies under ANY paradigm, not just rehabilitation)
If you were given an injury or limitation flag for this muscle_group ID (e.g. "knee", "lower back",
"shoulder"): every exercise that loads the affected joint/area MUST include (a) a concrete
pain-monitoring cue specific to that exercise - not a generic label like "knee-safe" - e.g. "stop
short of any pain; if depth provokes knee pain, reduce range of motion", and (b) a named fallback
substitute exercise to use if the prescribed movement does provoke pain (e.g. "if leg press
aggravates the knee, substitute hip thrust"). This applies regardless of paradigm - the
rehabilitation paradigm's own table above already handles the case where the GOAL itself is
recovery; this rule covers an injury flag under any OTHER paradigm (e.g. a hypertrophy plan for
someone with a knee injury).

## Output format for write_plan_memory (section_title = "{your muscle_group ID} - {ZONE LABEL}")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_exercise_recommender_prompt.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run the full suite**

Run: `pytest tests/ -q`
Expected: PASS, no regressions

- [ ] **Step 6: Commit**

```bash
git add prompts/exercise_recommender.md tests/test_exercise_recommender_prompt.py
git commit -m "$(cat <<'EOF'
Give concrete injury guidance under any paradigm, not just rehabilitation

The only injury-specific guidance anywhere was gated behind the
rehabilitation PARADIGM -- a hypertrophy plan for someone with a knee
injury got only a label ("knee-safe exercises... considerations"), never a
concrete pain cue or a named fallback substitute.
EOF
)"
```

---

### Task 8: Honest BF%/PBF framing (`prompts/plan_assembler.md`)

**Files:**
- Modify: `prompts/plan_assembler.md`
- Test: `tests/test_plan_assembler_prompt.py` (append)

**Interfaces:**
- Consumes: `config.load_prompt`
- Produces: nothing new — a prompt-content wording fix only.

**Confirmed root cause:** `prompts/exercise_recommender.md`'s Elevated BF% rule (unchanged by this plan) is already correctly framed as a "soft hint only... general lean" — it never claims to address body composition. The misleading claim is downstream: the real session's Recovery Notes state "Elevated body fat considerations addressed with moderate intensity and machine use for isolation" — that's the Plan Assembler's own synthesis for its output template's `{any BF% or sleep-based adjustments made}` line, and it overclaims "addressed" where the recommender's rule only ever said "lean."

- [ ] **Step 1: Write the failing test**

Append to `tests/test_plan_assembler_prompt.py`:

```python
def test_prompt_frames_bf_notes_as_a_lean_not_an_outcome():
    text = load_prompt("plan_assembler")
    assert "NEVER framed as" in text
    assert "nutrition/energy-balance outcome" in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_plan_assembler_prompt.py -v`
Expected: the existing test PASSES unchanged; the new test FAILS.

- [ ] **Step 3: Edit `prompts/plan_assembler.md`**

Replace:

```
### Recovery Notes
- {any asymmetry corrections to remind the user of}
- {any BF% or sleep-based adjustments made}
```

with:

```
### Recovery Notes
- {any asymmetry corrections to remind the user of}
- {any BF%-related rep-range lean, framed as what training LEANED TOWARD - e.g. "elevated BF%
  leaned rep selection toward the higher end of the hypertrophy range." NEVER framed as the
  workout "addressing," "resolving," or "considering" body composition as an outcome - body
  composition change is a nutrition/energy-balance outcome outside this program's scope, and this
  note must say so explicitly if a BF%-related lean is mentioned at all.}
- {any sleep-based adjustments made, separately from the BF% note above}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_plan_assembler_prompt.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full suite**

Run: `pytest tests/ -q`
Expected: PASS, no regressions

- [ ] **Step 6: Commit**

```bash
git add prompts/plan_assembler.md tests/test_plan_assembler_prompt.py
git commit -m "$(cat <<'EOF'
Frame BF%-related notes honestly as a lean, not an addressed outcome

A real session's Recovery Notes claimed "elevated body fat considerations
addressed with moderate intensity and machine use" -- misleading, since
body composition change is a nutrition/energy-balance outcome, not
something a rep-range lean resolves. The recommender's own Elevated BF%
rule was already correctly framed as a soft hint; only the assembler's
downstream synthesis overclaimed.
EOF
)"
```

---

### Task 9: Live regeneration + manual verification (integration)

**Files:**
- None modified — this is a verification-only task using the real intake and InBody scan the whole project was diagnosed against.

**Interfaces:**
- Consumes: the full pipeline as modified by Tasks 1-8 (`api/routes/plan.py`'s existing `/generate-plan` + `/generate-plan/stream/{session_id}` endpoints, unchanged).
- Produces: nothing — a manual verification checklist against a fresh, real plan generation.

Components 3-8 are prompt-content changes and are not unit-testable (non-deterministic LLM output). This task regenerates a plan from the exact same real intake used to diagnose all eight issues, then manually checks the fresh output against each fix — the same forensic method used to diagnose them in the first place.

- [ ] **Step 1: Confirm the server is running with all 8 prior tasks' changes applied**

```bash
curl -s http://localhost:8001/health
```

Expected: `{"status":"healthy",...}`. If not running, start it: `python main.py` (requires `.env` configured with `AZURE_OPENAI_*` and `ALLOW_DEV_LOGIN=true` — see `README.md`'s "Running it" section).

- [ ] **Step 2: Generate a plan from the exact real intake, using the real InBody image this session was diagnosed from**

```bash
python -c "
import requests, json

BASE = 'http://localhost:8001'
token = requests.post(f'{BASE}/auth/dev-login').json()['access_token']

with open('samples/inbody4.jfif', 'rb') as f:
    r = requests.post(f'{BASE}/generate-plan',
        headers={'Authorization': f'Bearer {token}'},
        files={'inbody_file': ('scan.jpg', f, 'image/jpeg')},
        data={
            'goal': 'hypertrophy',
            'days_per_week': 3,
            'experience': 'beginner',
            'session_duration': '45min',
            'injuries': 'knee',
            'priority': 'chest',
            'job_type': 'desk',
        })
r.raise_for_status()
session_id = r.json()['session_id']
print('session_id:', session_id)

stream = requests.get(f'{BASE}/generate-plan/stream/{session_id}',
    headers={'Authorization': f'Bearer {token}'}, stream=True, timeout=900)
for line in stream.iter_lines(decode_unicode=True):
    if not line or not line.startswith('data: '):
        continue
    event = json.loads(line[6:])
    if event.get('type') == 'done':
        print('DONE. error:', event.get('error'))
        break
"
```

Expected: prints a `session_id`, then `DONE. error: None` after several minutes (real agent pipeline run — Supervisor, 5 Exercise Recommender dispatches, Plan Assembler).

- [ ] **Step 3: Read the resulting plan and check each of the 8 fixes**

```bash
python -c "
from tools.memory import read_weekly_schedule
print(read_weekly_schedule('SESSION_ID_FROM_STEP_2'))
"
```

Manually verify against the printed plan:

1. **(Components 1-2) Volume budget honored:** every day's total scheduled sets is `<= 14` (this paradigm/duration's max_sets), and the Weekly Volume Summary's numbers match what's actually in the day tables above it (add them up yourself for at least one muscle group).
2. **(Component 3) Chest priority reflected:** chest's weekly total sits at or near the top of its target range (12 for beginner hypertrophy), not the same or lower than non-priority muscles.
3. **(Component 4) Push/pull balance:** no single day has more than one more pressing-pattern exercise than pulling-pattern exercise.
4. **(Component 5) Beginner-realistic exercise selection:** if a pull-up (or similar bodyweight compound) appears anywhere, it's either an assisted/regressed variant, or a rep target realistic for a stated beginner — not `4×12` on a strict pull-up.
5. **(Component 6) Rep-range differentiation:** compound lifts (bench press, squat, row, overhead press) and isolation movements (lateral raise, curl, pushdown, leg extension) do NOT all show the identical rep number — compounds should skew lower, isolation higher.
6. **(Component 7) Real injury guidance:** any exercise touching the knee includes a specific pain-monitoring cue and a named fallback substitute, not just a label like "knee-safe."
7. **(Component 8) Honest BF% framing:** the Recovery Notes describe the BF%-related adjustment as a rep-range lean, and explicitly state that body composition change is a nutrition/energy-balance outcome — it does not claim the workout "addresses" elevated body fat.
8. **(Non-goal, confirm unaffected) Asymmetry:** this session's InBody scan has no asymmetry flags — confirm the Recovery Notes still correctly say no asymmetry corrections were needed, same as before this plan's changes.

- [ ] **Step 4: Record the result**

If all 8 check out: this plan is complete. If any qualitative item (3-8) doesn't hold up, that's real signal the corresponding prompt wording needs another iteration — note specifically which one and why, since this is exactly the kind of gap this task exists to catch before considering the plan done.
