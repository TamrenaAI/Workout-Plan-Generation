"""
Shared markdown-schedule parsing primitives, used by both
pipeline/plan_finalize.py (deterministic volume-budget trimming/rewriting)
and pipeline/plan_parser.parse_weekly_schedule (read-only structured JSON
for the API) so both parse the same "### Day N" / pipe-table format the
same way instead of maintaining two independent parsers that could drift.
"""

import re
from pydantic import BaseModel

_SETS_X_REPS = re.compile(r"(\d+)\s*[×xX]\s*(\d+(?:-\d+)?)")
_SETS_UNKNOWN_SEP = re.compile(r"^(\d)\D+(\d+(?:-\d+)?)$")  # malformed "4\x7f12" -> sets=4, reps=12
_SETS_CONCAT = re.compile(r"^(\d)(\d+(?:-\d+)?)$")  # malformed "58" -> sets=5, reps=8

_DAY_MAP_LINE = re.compile(
    r"^Day\s+(\d+)\s*-.*?muscles\s*\[([^\]]+)\]\s*\|\s*max_sets:\s*(\d+)\s*\|\s*intensity:\s*(\S+)",
    re.IGNORECASE,
)
_NUMBERED_EXERCISE = re.compile(r"^(\d+)\.\s+(.+?)\s+\d+\s*[×xX]\s*\d+")

DAY_HEADING = re.compile(r"^###\s+Day\s+(\d+)\b")


def parse_day_map(content: str) -> dict:
    """Extract Day N metadata from plan header (budget, muscle groups, intensity zone).

    Shared so both enforce_volume_budget (plan_finalize.py) and the read-only
    JSON parser parse day prescriptions identically instead of drifting.
    Returns: {day_num: {"budget": int, "muscles": [str,...], "zone": str}}
    """
    day_map = {}
    for line in content.splitlines():
        match = _DAY_MAP_LINE.match(line.strip())
        if not match:
            continue
        day_num, muscles_raw, budget, zone = match.groups()
        muscles = [m.strip() for m in muscles_raw.split(",") if m.strip()]
        day_map[int(day_num)] = {"budget": int(budget), "muscles": muscles, "zone": zone}
    return day_map


def parse_group_ordinals(content: str, muscle: str, zone: str) -> dict:
    """Map exercise names to their ordinals within a muscle-zone section.

    Shared so both enforce_volume_budget (plan_finalize.py) and the read-only
    JSON parser identify which exercises are primary (ordinal 1) vs auxiliary
    using the same logic, ensuring consistent priority rules across tools.
    Returns: {exercise_name_lower: ordinal}
    """
    heading = f"## {muscle} - {zone}"
    idx = content.rfind(heading)
    if idx == -1:
        return {}
    section = content[idx:]
    end = section.find("\n---")
    if end != -1:
        section = section[:end]

    ordinals = {}
    for line in section.splitlines():
        match = _NUMBERED_EXERCISE.match(line.strip())
        if match:
            ordinal, name = match.groups()
            ordinals[name.strip().lower()] = int(ordinal)
    return ordinals


def extract_sets_reps(cell: str) -> "tuple[int, str] | None":
    """Parse sets and reps from a table cell, handling malformed separators.

    Shared so both enforce_volume_budget (plan_finalize.py) and the read-only
    JSON parser tolerate real-world formatting issues (stray bytes, missing
    separators) the same way instead of silently failing on identical inputs.
    Handles: "4×12", "4x12", "4\x7f12" (stray byte), "4?12", "58" (collapsed).
    Returns: (sets: int, reps: str) or None if unparseable.
    """
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


def split_row(line: str) -> list:
    """Split a pipe-delimited markdown table row into cells.

    Shared so both enforce_volume_budget (plan_finalize.py) and the read-only
    JSON parser parse the same markdown table format the same way, handling
    leading/trailing pipe characters consistently.
    Returns: list of trimmed cell contents.
    """
    cells = [c.strip() for c in line.split("|")]
    if cells and cells[0] == "":
        cells.pop(0)
    if cells and cells[-1] == "":
        cells.pop()
    return cells


class ParsedExercise(BaseModel):
    """One exercise row parsed from a weekly-schedule table.

    Fields replaced_from and adjustment_reason are populated by the API route
    (not by parse_weekly_schedule itself) when the AI-driven swap detector
    identifies an exercise substitution.
    """
    name: str
    sets: "int | None" = None
    reps: "str | None" = None
    rest: "str | None" = None
    rpe: "str | None" = None
    muscle_group: "str | None" = None
    replaced_from: "str | None" = None
    adjustment_reason: "str | None" = None


class ParsedDay(BaseModel):
    """One training day parsed from a '### Day N' schedule section.

    Used by GET /sessions/{id}/plan to return structured schedule data
    instead of relying on a client-side mock disconnected from the real plan.
    """
    day_number: int
    label: str
    target_focus: str
    warmup: "str | None" = None
    exercises: "list[ParsedExercise]" = []


def parse_weekly_schedule(full_plan_content: str) -> "list[ParsedDay]":
    """Structured, read-only counterpart to enforce_volume_budget: parses
    the LAST '## Weekly Schedule' section into ParsedDay/ParsedExercise
    objects for GET /sessions/{id}/plan to return as JSON, instead of the
    frontend either showing raw markdown or (as found during design) a
    hardcoded mock disconnected from the real plan entirely.

    full_plan_content must be the WHOLE plan.md file (tools.memory.
    read_full_plan), not just tools.memory.read_weekly_schedule's return
    value — the DAY MAP and per-muscle-group exercise lists this needs for
    target_focus/muscle_group live earlier in the file, outside the
    schedule section itself.

    Same conservative stance as plan_finalize.py: unparseable days/rows are
    skipped rather than raising — returns whatever DOES parse.
    """
    from tools.memory import find_last_schedule_marker

    marker = find_last_schedule_marker(full_plan_content)
    if marker is None:
        return []
    schedule_idx, _heading = marker
    day_map = parse_day_map(full_plan_content)

    lines = full_plan_content[schedule_idx:].splitlines()
    tail_marker_idx = None
    for i, line in enumerate(lines):
        if i == 0:
            # Line 0 is the '## Weekly Schedule' heading itself — don't treat
            # it as its own tail marker.
            continue
        stripped = line.strip()
        if (
            stripped.startswith("### Weekly Volume Summary")
            or stripped.startswith("### Recovery Notes")
            or stripped.startswith("## ")
        ):
            # A bare '## ' heading (not just the two known '###' tail
            # markers above) also ends the schedule section — e.g.
            # agents/plan_adjuster.py appends a trailing
            # '## Plan Adjustment — {day_label}' section to plan.md after
            # every feedback-driven swap, and its prose (which may contain
            # lines starting with '|') must never be absorbed into the last
            # day's exercise table.
            tail_marker_idx = i
            break
    day_lines_all = lines[1:tail_marker_idx] if tail_marker_idx is not None else lines[1:]

    day_blocks = []
    current = None
    for line in day_lines_all:
        heading = DAY_HEADING.match(line.strip())
        if heading:
            current = (int(heading.group(1)), [line])
            day_blocks.append(current)
        elif current is not None:
            current[1].append(line)

    parsed_days = []
    for day_num, day_lines in day_blocks:
        day_info = day_map.get(day_num, {})
        muscles = day_info.get("muscles", [])
        zone = day_info.get("zone", "")

        muscle_by_name = {}
        for muscle in muscles:
            for name in parse_group_ordinals(full_plan_content, muscle, zone):
                if name not in muscle_by_name:
                    muscle_by_name[name] = muscle

        label = re.sub(r"^###\s+", "", day_lines[0].strip())
        warmup = None
        table_start = None
        table_end = None
        for i, line in enumerate(day_lines):
            stripped = line.strip()
            if warmup is None and stripped.startswith("**Warm-up:**"):
                warmup = stripped[len("**Warm-up:**"):].strip()
            if stripped.startswith("|"):
                if table_start is None:
                    table_start = i
                table_end = i

        exercises = []
        if table_start is not None:
            for row_line in day_lines[table_start + 2: table_end + 1]:
                cells = split_row(row_line)
                if len(cells) < 5:
                    continue
                name = cells[1]
                sets_reps = extract_sets_reps(cells[2])
                sets, reps = sets_reps if sets_reps else (None, None)
                exercises.append(ParsedExercise(
                    name=name,
                    sets=sets,
                    reps=reps,
                    rest=cells[3] or None,
                    rpe=cells[4] or None,
                    muscle_group=muscle_by_name.get(name.strip().lower()),
                ))

        parsed_days.append(ParsedDay(
            day_number=day_num,
            label=label,
            target_focus=", ".join(m.upper() for m in muscles),
            warmup=warmup,
            exercises=exercises,
        ))

    parsed_days.sort(key=lambda d: d.day_number)
    return parsed_days
