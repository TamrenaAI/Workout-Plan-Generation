"""
Shared MD memory file + structured progress tracking.

All agents communicate through a single markdown file per session
(sessions/{session_id}/plan.md) — read the whole file first, append a
section when done. Sequential execution means no concurrent-write conflicts.

Progress tracking is a separate JSON file (sessions/{session_id}/progress.json),
written and read only through these structured tool functions — never parsed
back out of the free-form markdown prose. See tamrena_architecture_2.md
Section 5d for why: an earlier run silently dropped a fully-planned muscle
group because the Supervisor's only way to know what was "done" was to
re-read its own dispatch history or regex the MD file.
"""

import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone

from langchain_core.tools import tool

from config import SESSION_DIR
from tools.dynamo import get_plan_adjustments_table, get_workout_feedback_table

# Guards progress.json's read-modify-write cycle. deepagents can execute
# multiple task() dispatches concurrently (a ThreadPoolExecutor within this
# same process) when the Supervisor emits more than one tool call in a
# single turn. Without this lock, two exercise-recommenders finishing at
# nearly the same moment can each read a stale copy of progress.json and
# clobber each other's mark_step_done write — the Supervisor then sees a
# muscle group as "missing" and re-dispatches it, even though it actually
# completed. See prompts/supervisor.md's dispatch rule for the other half of
# this fix (only one task() call per turn, so this race shouldn't occur in
# practice) — this lock is the belt-and-suspenders guarantee against data
# corruption regardless of whether that rule is ever violated.
_progress_lock = threading.Lock()


def _plan_path(session_id: str) -> str:
    return os.path.join(SESSION_DIR, session_id, "plan.md")


def _progress_path(session_id: str) -> str:
    return os.path.join(SESSION_DIR, session_id, "progress.json")


# prompts/plan_assembler.md only ever instructs writing under "Weekly
# Schedule" (step 3), but the assembler has been observed to also
# independently write a second, later copy of the same days under a
# different self-chosen heading as part of its own step 5 "return the plan"
# behavior (see sessions/dfd4454f-...: a full second copy under "## Full
_SCHEDULE_HEADINGS = (
    "## Weekly Schedule",
    "## Full Workout Plan",
    "## Workout Plan",
    "## Training Schedule",
    "## Routine Schedule",
    "## Workout Routine",
    "## Weekly Routine",
    "## Training Protocol",
)


def find_last_schedule_marker(content: str) -> "tuple[int, str] | None":
    """Returns (index, heading) of whichever known schedule heading occurs
    LAST in the file, or searches regex patterns / Day 1 markers."""
    best = None
    for heading in _SCHEDULE_HEADINGS:
        idx = content.lower().rfind(heading.lower())
        if idx != -1 and (best is None or idx > best[0]):
            best = (idx, heading)

    if best is None:
        # Check regex for markdown headings containing schedule/workout/training
        matches = list(re.finditer(r"(?im)^#{1,4}\s*(?:weekly\s+schedule|full\s+workout\s+plan|workout\s+plan|training\s+plan|workout\s+schedule)", content))
        if matches:
            last_match = matches[-1]
            best = (last_match.start(), last_match.group(0))

    if best is None:
        # Fallback: find leading "### Day 1" or "## Day 1"
        matches = list(re.finditer(r"(?im)^#{2,4}\s*Day\s*1\b", content))
        if matches:
            last_match = matches[-1]
            best = (last_match.start(), last_match.group(0))

    return best


def read_weekly_schedule(session_id: str) -> str | None:
    path = _plan_path(session_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if not content.strip():
        return None
    marker = find_last_schedule_marker(content)
    if marker is None:
        # If content has any markdown table with exercise rows, return full content
        if "|" in content and ("Day" in content or "Set" in content):
            return content.strip()
        return None
    idx, _heading = marker
    section = content[idx:].rstrip()
    if section.endswith("---"):
        section = section[: -len("---")].rstrip()
    return section


def read_full_plan(session_id: str) -> "str | None":
    """The raw plan.md content, unlike read_weekly_schedule which returns
    only the last schedule section. pipeline.plan_parser.parse_weekly_schedule
    needs the DAY MAP and per-muscle-group exercise lists that live earlier
    in the file, outside the schedule section itself. Returns None if the
    plan file doesn't exist yet."""
    path = _plan_path(session_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def read_progress_report(session_id: str) -> "str | None":
    """Reads the '## Progress Report' section the Progress Analyst wrote via
    write_plan_memory into the NEW session's plan.md (see
    agents/progress_analyst.py) — the deterministic, tool-written source of
    truth for the narrative, preferred over trusting the agent's own final
    chat reply (same rationale as read_weekly_schedule above)."""
    path = _plan_path(session_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    idx = content.rfind("## Progress Report")
    if idx == -1:
        return None
    section = content[idx:].rstrip()
    if section.endswith("---"):
        section = section[: -len("---")].rstrip()
    return section


@tool
def read_plan_memory(session_id: str) -> str:
    """Read the full shared plan memory file for this session. Call this first before doing any work."""
    path = _plan_path(session_id)
    if not os.path.exists(path):
        return "(plan file not created yet)"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@tool
def write_plan_memory(session_id: str, section_title: str, content: str) -> str:
    """Append a completed section to the shared plan memory file. Never call this more than once per section."""
    path = _plan_path(session_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"\n\n## {section_title}\n{content}\n\n---")
    return f"Written to plan memory: {section_title}"


@tool
def validate_session_duration(session_id: str) -> str:
    """
    Plan Assembler calls this AFTER writing the Weekly Schedule. Parses the DAY MAP's
    max_sets budgets and the scheduled sets per day from the Weekly Schedule section,
    and returns PASS or the specific days/set-counts that are over budget.
    """
    path = _plan_path(session_id)
    if not os.path.exists(path):
        return "NO PLAN FILE FOUND — cannot validate."
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # parse DAY MAP lines: "Day 1 — Legs: muscles [...] | max_sets: 26 | intensity: medium"
    day_budgets = {}
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("Day ") and "max_sets:" in stripped:
            day_match = re.match(r"Day \d+", stripped)
            if not day_match:
                continue
            day_label = day_match.group(0)
            try:
                max_sets = int(stripped.split("max_sets:")[1].split("|")[0].strip())
                day_budgets[day_label] = max_sets
            except (ValueError, IndexError):
                continue

    if not day_budgets:
        return "NO DAY MAP FOUND — cannot validate. Supervisor must write DAY MAP before dispatching agents."

    # count scheduled sets per day from "### Day N — ..." sections + "N×M" table cells
    day_set_counts = {}
    current_day = None
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("### Day"):
            day_match = re.match(r"Day \d+", stripped.replace("###", "").strip())
            if not day_match:
                continue
            current_day = day_match.group(0)
            day_set_counts[current_day] = 0
        elif current_day and stripped.startswith("|"):
            for part in stripped.split("|"):
                match = re.search(r"(\d+)\s*[×xX]\s*\d+", part.strip())
                if match:
                    day_set_counts[current_day] += int(match.group(1))

    violations = []
    for day, budget in day_budgets.items():
        if day not in day_set_counts:
            violations.append(f"  {day}: no schedule table found for this day — cannot verify budget")
            continue
        scheduled = day_set_counts[day]
        if scheduled > budget:
            violations.append(f"  {day}: {scheduled} sets scheduled, budget is {budget} ({scheduled - budget} over — trim)")

    if not violations:
        return "PASS — all days within session duration budget."
    return "VIOLATIONS — trim before writing final plan:\n" + "\n".join(violations)


@tool
def init_plan_progress(session_id: str, muscle_groups: list[str]) -> str:
    """Supervisor calls this ONCE, right after deciding the split and writing the DAY MAP —
    before dispatching any exercise-recommender. muscle_groups must be the complete,
    authoritative list of muscle-group ids this plan requires (e.g. including separate
    ids like 'legs_a'/'legs_b' when there are two leg days)."""
    path = _progress_path(session_id)
    with _progress_lock:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"expected": muscle_groups, "completed": []}, f)
    return f"Progress tracker initialized: {len(muscle_groups)} muscle groups expected: {muscle_groups}"


@tool
def mark_step_done(session_id: str, muscle_group: str) -> str:
    """Exercise-recommender calls this as its LAST action, immediately after write_plan_memory,
    using the exact muscle_group id it was given in its task prompt."""
    path = _progress_path(session_id)
    with _progress_lock:
        if not os.path.exists(path):
            return "WARNING: progress tracker not initialized for this session."
        with open(path, "r", encoding="utf-8") as f:
            progress = json.load(f)

        if muscle_group not in progress["expected"]:
            return f"WARNING: '{muscle_group}' is not in the expected list {progress['expected']}. Not recorded."
        if muscle_group in progress["completed"]:
            return f"WARNING: '{muscle_group}' was already marked done — possible duplicate dispatch."

        progress["completed"].append(muscle_group)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(progress, f)

        remaining = [g for g in progress["expected"] if g not in progress["completed"]]
    return f"Marked done: {muscle_group}. Remaining: {remaining or 'none — all groups complete'}"


@tool
def get_plan_progress(session_id: str) -> str:
    """Supervisor calls this after EVERY task() return, to confirm the muscle group just
    dispatched actually got marked done before deciding what to dispatch next. Also call
    before dispatching the plan-assembler — only proceed if all_done is true."""
    path = _progress_path(session_id)
    with _progress_lock:
        if not os.path.exists(path):
            return json.dumps({"error": "progress tracker not initialized"})
        with open(path, "r", encoding="utf-8") as f:
            progress = json.load(f)
    remaining = [g for g in progress["expected"] if g not in progress["completed"]]
    return json.dumps({
        "expected": progress["expected"],
        "completed": progress["completed"],
        "remaining": remaining,
        "next": remaining[0] if remaining else None,
        "all_done": len(remaining) == 0,
    })


@tool
def validate_plan_completeness(session_id: str) -> str:
    """Plan Assembler calls this FIRST, before doing any scheduling work. Returns PASS only
    if every expected muscle group has been marked done."""
    result = json.loads(get_plan_progress.invoke({"session_id": session_id}))
    if result.get("all_done"):
        return "PASS — all expected muscle groups have prescriptions."
    return f"INCOMPLETE — missing prescriptions for: {result.get('remaining')}. Do not assemble the plan."


@tool
def record_exercise_adjustment(
    session_id: str,
    day_label: str,
    exercise_name: str,
    reason: str,
    new_exercise_name: str | None = None,
    sets: int | None = None,
    reps: str | None = None,
    rpe: int | None = None,
) -> str:
    """Plan Adjuster calls this ONCE per flagged exercise it adjusts, in addition to (not
    instead of) write_plan_memory's prose section. This is the structured record the API
    route hands back to the frontend so it can update the exercise actually displayed in the
    user's plan — write_plan_memory's markdown is for human narrative only and is never
    parsed back out (see this module's docstring).

    exercise_name: the ORIGINAL exercise name as it appears in plan memory — required so the
        frontend can find what to replace/update.
    new_exercise_name: set only when substituting the exercise entirely (pain=true case).
        Leave None for a pure volume/intensity change to the same exercise.
    sets, reps, rpe: the NEW value only for whichever of these actually changed. Leave the
        others None.
    reason: one sentence, referencing the specific feedback that triggered this adjustment.
    """
    get_plan_adjustments_table().put_item(Item={
        "adjustment_id": str(uuid.uuid4()),
        "session_day_key": f"{session_id}#{day_label}",
        "session_id": session_id,
        "day_label": day_label,
        "exercise_name": exercise_name,
        "new_exercise_name": new_exercise_name,
        "sets": sets,
        "reps": reps,
        "rpe": rpe,
        "reason": reason,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return f"Recorded structured adjustment for: {exercise_name}"


def _decimal_to_int(value):
    """DynamoDB's Number type always deserializes to Decimal — sets/rpe are
    plain ints on write (see record_exercise_adjustment) and callers (e.g.
    api/routes/plan.py) expect plain ints back, same convention as
    pipeline/monthly_progress.py's Decimal->int/float conversions."""
    return int(value) if value is not None else None


def read_exercise_adjustments(session_id: str, day_label: str, since: "datetime") -> list[dict]:
    """Plain function (not an agent tool) for the API route to call directly after the Plan
    Adjuster finishes, to fetch the structured adjustments it just recorded via
    record_exercise_adjustment. `since` scopes the query to this invocation's run so an
    earlier adjustment for the same day_label isn't returned again."""
    resp = get_plan_adjustments_table().query(
        IndexName="session-day-index",
        KeyConditionExpression="session_day_key = :key AND created_at >= :since",
        ExpressionAttributeValues={
            ":key": f"{session_id}#{day_label}",
            ":since": since.isoformat(),
        },
        ScanIndexForward=True,
    )
    return [
        {
            "exercise_name": d["exercise_name"],
            "new_exercise_name": d.get("new_exercise_name"),
            "sets": _decimal_to_int(d.get("sets")),
            "reps": d.get("reps"),
            "rpe": _decimal_to_int(d.get("rpe")),
            "reason": d["reason"],
        }
        for d in resp["Items"]
    ]


def read_all_exercise_adjustments(session_id: str) -> list[dict]:
    """Every structured adjustment ever recorded for this session, oldest
    first (so a later re-swap of the same exercise wins when matching by
    name in GET /sessions/{id}/plan) — unlike read_exercise_adjustments,
    not scoped to one day_label or one invocation's `since` window. Lets
    the plan-table endpoint show "AI Replaced" on whatever exercise is
    CURRENTLY in the plan, persisted across page reloads instead of only
    right after the feedback call that triggered the swap.

    No GSI covers "all adjustments for a session" — the session-day index
    is keyed on session_id#day_label, and querying it would require
    already knowing every day_label in advance. Falls back to a filtered
    scan; acceptable given this query's low frequency (page load, not hot
    path)."""
    resp = get_plan_adjustments_table().scan(
        FilterExpression="session_id = :sid",
        ExpressionAttributeValues={":sid": session_id},
    )
    items = resp["Items"]
    while "LastEvaluatedKey" in resp:
        resp = get_plan_adjustments_table().scan(
            FilterExpression="session_id = :sid",
            ExpressionAttributeValues={":sid": session_id},
            ExclusiveStartKey=resp["LastEvaluatedKey"],
        )
        items.extend(resp["Items"])
    items.sort(key=lambda d: d["created_at"])
    return [
        {
            "day_label": d.get("day_label"),
            "exercise_name": d["exercise_name"],
            "new_exercise_name": d.get("new_exercise_name"),
            "sets": _decimal_to_int(d.get("sets")),
            "reps": d.get("reps"),
            "rpe": _decimal_to_int(d.get("rpe")),
            "reason": d["reason"],
        }
        for d in items
    ]


@tool
def read_workout_feedback(session_id: str) -> str:
    """Plan Adjuster calls this to see every post-workout feedback submission recorded for
    this session so far, most recent last. Feedback is written by the API route (via
    pipeline/workout_feedback.py), not by any agent — this is the read side only, kept here
    rather than in pipeline/workout_feedback.py per this repo's tools/ vs pipeline/ rule
    (writing is a pipeline concern, reading is a tool concern; tools/ must not import from
    pipeline/ — see this file's module docstring)."""
    resp = get_workout_feedback_table().query(
        IndexName="session-index",
        KeyConditionExpression="session_id = :sid",
        ExpressionAttributeValues={":sid": session_id},
        ScanIndexForward=True,
    )
    docs = resp["Items"]
    submissions = [
        {
            "day_label": d["day_label"],
            "exercises": d["exercises"],
            "adjustment_triggered": d["adjustment_triggered"],
            "submitted_at": d["submitted_at"],
        }
        for d in docs
    ]
    if not submissions:
        return "(no feedback submitted yet for this session)"
    return json.dumps(submissions)
