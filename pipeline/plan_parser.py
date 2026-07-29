"""
Shared markdown-schedule parsing primitives, used by both
pipeline/plan_finalize.py (deterministic volume-budget trimming/rewriting)
and pipeline/plan_parser.parse_weekly_schedule (read-only structured JSON
for the API) so both parse the same "### Day N" / pipe-table format the
same way instead of maintaining two independent parsers that could drift.
"""

import re

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
    """Day number -> {"budget": int, "muscles": [str,...], "zone": str}."""
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
    """Last '## {muscle} - {zone}' section -> {exercise_name_lower: ordinal}."""
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
    cells = [c.strip() for c in line.split("|")]
    if cells and cells[0] == "":
        cells.pop(0)
    if cells and cells[-1] == "":
        cells.pop()
    return cells
