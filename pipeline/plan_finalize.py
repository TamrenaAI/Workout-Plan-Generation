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

import re

from pipeline.plan_parser import (
    DAY_HEADING as _DAY_HEADING,
    extract_sets_reps as _extract_sets_reps,
    parse_day_map as _parse_day_map,
    parse_group_ordinals as _parse_group_ordinals,
    split_row as _split_row,
)
from tools.memory import _plan_path, find_last_schedule_marker, write_plan_memory

_GROUP_HEADING = re.compile(r"^##\s+(\S+)\s*-\s*(\S+)\s*$")
_VOLUME_ROW = re.compile(r"^\|\s*([A-Za-z_]+)\s*\|\s*(\d+)\s*\|\s*([\d]+-[\d]+|\S+)\s*\|\s*(\S+)\s*\|$")

MIN_SETS_FLOOR = 2


def _extract_sets(cell: str) -> "int | None":
    result = _extract_sets_reps(cell)
    return result[0] if result else None


def _parse_target_range(cell: str) -> "tuple[int, int] | None":
    match = re.match(r"^(\d+)-(\d+)$", cell.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


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
    path = _plan_path(session_id)
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return False

    day_map = _parse_day_map(content)
    marker = find_last_schedule_marker(content)
    if not day_map or marker is None:
        return False
    schedule_idx, _heading = marker

    schedule_section = content[schedule_idx:]
    lines = schedule_section.splitlines()

    # Everything from "### Weekly Volume Summary" (or "### Recovery Notes" if no
    # summary present) to the end of the section is preserved/rewritten separately;
    # day blocks are only parsed from the lines before that marker.
    tail_marker_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("### Weekly Volume Summary") or line.strip().startswith("### Recovery Notes"):
            tail_marker_idx = i
            break
    tail_lines = lines[tail_marker_idx:] if tail_marker_idx is not None else []
    day_lines_all = lines[1:tail_marker_idx] if tail_marker_idx is not None else lines[1:]

    day_blocks = []  # (day_num, [lines])
    current = None
    for line in day_lines_all:
        heading = _DAY_HEADING.match(line.strip())
        if heading:
            current = (int(heading.group(1)), [line])
            day_blocks.append(current)
        elif current is not None:
            current[1].append(line)

    if not day_blocks:
        return False

    any_day_trimmed = False
    muscle_week_totals: dict = {}
    rebuilt_days = []

    for day_num, day_lines in day_blocks:
        day_info = day_map.get(day_num)
        if not day_info:
            rebuilt_days.append(day_lines)
            continue

        ordinal_lookup = {}
        for muscle in day_info["muscles"]:
            for name, ordinal in _parse_group_ordinals(content, muscle, day_info["zone"]).items():
                if name not in ordinal_lookup:
                    ordinal_lookup[name] = (ordinal, muscle)

        table_start = None
        table_end = None
        for i, line in enumerate(day_lines):
            if line.strip().startswith("|"):
                if table_start is None:
                    table_start = i
                table_end = i
        if table_start is None:
            rebuilt_days.append(day_lines)
            continue

        header_row = re.sub(r"(Sets\s*)\S(\s*Reps)", r"\1×\2", day_lines[table_start])
        separator_row = day_lines[table_start + 1]
        data_rows = day_lines[table_start + 2: table_end + 1]

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

        total = sum(r["sets"] or 0 for r in rows)
        budget = day_info["budget"]

        if total > budget:
            any_day_trimmed = True

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

        for r in rows:
            if r["muscle"] and r["sets"]:
                muscle_week_totals[r["muscle"]] = muscle_week_totals.get(r["muscle"], 0) + r["sets"]

        rebuilt_row_lines = []
        for idx, r in enumerate(rows, start=1):
            cells = list(r["cells"])
            cells[0] = str(idx)
            if r["sets"] is not None and r["reps"] is not None:
                cells[2] = f"{r['sets']}×{r['reps']}"
            rebuilt_row_lines.append("| " + " | ".join(cells) + " |")

        rebuilt_days.append(
            day_lines[:table_start] + [header_row, separator_row] + rebuilt_row_lines + day_lines[table_end + 1:]
        )

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
