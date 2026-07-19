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

from langchain_core.tools import tool

from config import SESSION_DIR

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


def read_weekly_schedule(session_id: str) -> str | None:
    """Reads the LAST '## Weekly Schedule' section written to plan.md by the
    Plan Assembler's write_plan_memory call — the deterministic, tool-written
    source of truth for the assembled exercises.

    Used as the text actually returned to the user instead of the
    Supervisor's own free-text final chat reply: asking the model to
    "synthesise and return" a long multi-table plan it already produced via
    a tool call is a second, independent generation with no fidelity
    guarantee, and it has been observed to summarize or drop exercise rows
    that plan.md has intact. A retried/re-dispatched session can have more
    than one '## Weekly Schedule' section (see mark_step_done's duplicate-
    dispatch guard) — the last one written is the current, authoritative
    plan, hence rfind rather than find.

    Returns None if the plan file doesn't exist yet or the Assembler hasn't
    written a schedule yet (e.g. the pipeline failed before that step) —
    callers should fall back to the Supervisor's own reply in that case.
    """
    path = _plan_path(session_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    marker = "## Weekly Schedule"
    idx = content.rfind(marker)
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
