"""
Tests for GET /sessions/{session_id}/plan — fetching a session's persisted
weekly schedule any time after generation finishes, not just live via the
SSE stream (the gap flagged when the mobile app was wired up: there was no
way to fetch a "current plan" outside of that one-time stream).
"""

import os
import sys
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import ownership
from auth import tokens
from tools import memory as tools_memory
from tools.dynamo import get_plan_adjustments_table


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(tools_memory, "SESSION_DIR", str(tmp_path))
    monkeypatch.setattr(tokens, "JWT_SECRET", "test-secret-do-not-use-in-real-envs")


def _make_user(sub: str) -> dict:
    # This service no longer owns `users` (see
    # docs/superpowers/specs/2026-07-25-bff-auth-handoff-design.md) — a
    # fresh uuid4 is all any test needs, since every route here only
    # ever reads the id. `sub` is kept as a parameter purely so call sites
    # stay readable (e.g. `_make_user("cv-owner")`); it's not used for
    # deduplication anymore, each call already produces a distinct id.
    return {"id": str(uuid.uuid4())}


def test_returns_404_for_unowned_session():
    import api.main as m

    owner = _make_user("owner")
    other = _make_user("other")
    ownership.create_session("s1", user_id=owner["id"], goal="hypertrophy")

    client = TestClient(m.app)
    token = tokens.create_access_token(user_id=other["id"])
    r = client.get("/sessions/s1/plan", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


def test_pending_when_no_schedule_written_yet():
    import api.main as m

    owner = _make_user("owner2")
    ownership.create_session("s2", user_id=owner["id"], goal="hypertrophy")

    client = TestClient(m.app)
    token = tokens.create_access_token(user_id=owner["id"])
    r = client.get("/sessions/s2/plan", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending"
    assert body["plan"] is None


def test_failed_when_pipeline_errored():
    import api.main as m

    owner = _make_user("owner4")
    session_id = "s4"
    ownership.create_session(session_id, user_id=owner["id"], goal="hypertrophy")
    ownership.update_session_status(session_id, "failed", error="Supervisor pipeline crashed")

    client = TestClient(m.app)
    token = tokens.create_access_token(user_id=owner["id"])
    r = client.get(f"/sessions/{session_id}/plan", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "failed"
    assert body["error"] == "Supervisor pipeline crashed"
    assert body["plan"] is None


def test_ready_response_includes_parsed_days_and_swap_badge():
    import api.main as m
    from auth import ownership
    from tools import memory as tools_memory

    owner = _make_user("owner5")
    session_id = "s5"
    ownership.create_session(session_id, user_id=owner["id"], goal="hypertrophy")

    full_plan = """

## User Profile + Plan Header
Day 1 - hard: muscles [chest] | max_sets: 10 | intensity: hard

---

## chest - hard
1. Flat Barbell Bench Press 4x8 | Rest 2-3 min | RPE 8
   -> heavy compound pressing.
2. Cable Fly 3x12 | Rest 90s | RPE 7
   -> isolation.

Evidence: compound presses prioritized.

---

## Weekly Schedule
### Day 1 -- Monday: Push (Chest) - Hard Session
**Warm-up:** Dynamic shoulder circles.

| # | Exercise | Sets x Reps | Rest | RPE |
|---|----------|-------------|------|-----|
| 1 | Flat Barbell Bench Press | 4x8 | 2-3 min | 8 |
| 2 | Cable Fly | 3x12 | 90s | 7 |

**Coaching notes:** Focus on controlled eccentrics.
"""
    session_dir = os.path.join(tools_memory.SESSION_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    with open(os.path.join(session_dir, "plan.md"), "w", encoding="utf-8") as f:
        f.write(full_plan)

    # The Weekly Schedule table above still says "Cable Fly" — the Plan
    # Adjuster deliberately never rewrites it (prompts/plan_adjuster.md:
    # "do not ask to overwrite the original muscle-group section"). The
    # structured adjustment record below is what get_session_plan uses to
    # substitute the displayed exercise.
    day_label = "Day 1 -- Monday: Push (Chest) - Hard Session"
    get_plan_adjustments_table().put_item(Item={
        "adjustment_id": str(uuid.uuid4()),
        "session_day_key": f"{session_id}#{day_label}",
        "session_id": session_id, "day_label": day_label,
        "exercise_name": "Cable Fly", "new_exercise_name": "Machine Chest Press",
        "sets": None, "reps": None, "rpe": None,
        "reason": "Reported shoulder pain on Cable Fly",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    client = TestClient(m.app)
    token = tokens.create_access_token(user_id=owner["id"])
    r = client.get(f"/sessions/{session_id}/plan", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["days"] is not None
    day1 = body["days"][0]
    assert day1["day_number"] == 1
    exercises_by_name = {e["name"]: e for e in day1["exercises"]}
    assert exercises_by_name["Flat Barbell Bench Press"]["replaced_from"] is None
    assert "Cable Fly" not in exercises_by_name
    swapped = exercises_by_name["Machine Chest Press"]
    assert swapped["replaced_from"] == "Cable Fly"
    assert swapped["adjustment_reason"] == "Reported shoulder pain on Cable Fly"


def test_swap_badges_are_scoped_per_day_not_leaked_across_days():
    """Regression test for a review finding: the adjustments lookup used to be
    keyed by exercise name alone, session-wide. If two different days each had
    an adjustment whose ORIGINAL exercise_name collided, a flat dict would
    silently keep only the last-inserted entry and adjust the OTHER day's
    exercise with the wrong replaced_from/adjustment_reason. Here Day 1 and
    Day 2 each swap a different original exercise into the same new exercise
    ("Machine Chest Press"), proving each day's adjustment is applied to its
    own exercise independently. Also exercises the case-insensitive
    exercise-name matching path (Day 1's adjustment stores its ORIGINAL
    exercise_name in a different case than the schedule table)."""
    import api.main as m
    from auth import ownership
    from tools import memory as tools_memory

    owner = _make_user("owner7")
    session_id = "s7"
    ownership.create_session(session_id, user_id=owner["id"], goal="hypertrophy")

    full_plan = """

## User Profile + Plan Header
Day 1 - hard: muscles [chest] | max_sets: 10 | intensity: hard
Day 2 - hard: muscles [chest] | max_sets: 10 | intensity: hard

---

## chest - hard
1. Flat Barbell Bench Press 4x8 | Rest 2-3 min | RPE 8
   -> heavy compound pressing.
2. Cable Fly 3x12 | Rest 90s | RPE 7
   -> isolation.
3. Incline Dumbbell Press 4x10 | Rest 2 min | RPE 8
   -> upper chest emphasis.

Evidence: compound presses prioritized.

---

## Weekly Schedule
### Day 1 -- Monday: Push (Chest) - Hard Session
**Warm-up:** Dynamic shoulder circles.

| # | Exercise | Sets x Reps | Rest | RPE |
|---|----------|-------------|------|-----|
| 1 | Flat Barbell Bench Press | 4x8 | 2-3 min | 8 |
| 2 | Cable Fly | 3x12 | 90s | 7 |

**Coaching notes:** Focus on controlled eccentrics.

### Day 2 -- Thursday: Push (Chest) - Hard Session
**Warm-up:** Dynamic shoulder circles.

| # | Exercise | Sets x Reps | Rest | RPE |
|---|----------|-------------|------|-----|
| 1 | Incline Dumbbell Press | 4x10 | 2 min | 8 |

**Coaching notes:** Focus on controlled eccentrics.
"""
    session_dir = os.path.join(tools_memory.SESSION_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    with open(os.path.join(session_dir, "plan.md"), "w", encoding="utf-8") as f:
        f.write(full_plan)

    now = datetime.now(timezone.utc).isoformat()
    day1_label = "Day 1 -- Monday: Push (Chest) - Hard Session"
    day2_label = "Day 2 -- Thursday: Push (Chest) - Hard Session"
    table = get_plan_adjustments_table()
    table.put_item(Item={
        "adjustment_id": str(uuid.uuid4()),
        "session_day_key": f"{session_id}#{day1_label}",
        "session_id": session_id, "day_label": day1_label,
        "exercise_name": "CABLE FLY", "new_exercise_name": "Machine Chest Press",
        "sets": None, "reps": None, "rpe": None,
        "reason": "Day 1 reason: shoulder pain on Cable Fly",
        "created_at": now,
    })
    table.put_item(Item={
        "adjustment_id": str(uuid.uuid4()),
        "session_day_key": f"{session_id}#{day2_label}",
        "session_id": session_id, "day_label": day2_label,
        "exercise_name": "Incline Dumbbell Press", "new_exercise_name": "Machine Chest Press",
        "sets": None, "reps": None, "rpe": None,
        "reason": "Day 2 reason: wrist discomfort on Incline Dumbbell Press",
        "created_at": now,
    })

    client = TestClient(m.app)
    token = tokens.create_access_token(user_id=owner["id"])
    r = client.get(f"/sessions/{session_id}/plan", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    days_by_number = {d["day_number"]: d for d in body["days"]}

    day1_swapped = {e["name"]: e for e in days_by_number[1]["exercises"]}["Machine Chest Press"]
    assert day1_swapped["replaced_from"] == "Cable Fly"
    assert day1_swapped["adjustment_reason"] == "Day 1 reason: shoulder pain on Cable Fly"

    day2_swapped = {e["name"]: e for e in days_by_number[2]["exercises"]}["Machine Chest Press"]
    assert day2_swapped["replaced_from"] == "Incline Dumbbell Press"
    assert day2_swapped["adjustment_reason"] == "Day 2 reason: wrist discomfort on Incline Dumbbell Press"


def test_swap_badge_matches_via_day_prefix_when_day_label_format_drifts():
    """Regression test for a review finding: day_label on a plan_adjustments
    doc is whatever the LLM-driven Plan Adjuster agent passed to
    record_exercise_adjustment — its exact format isn't constrained to match
    ParsedDay.label byte-for-byte. Here the adjustment is recorded with the
    short "Day 1" instead of the full "Day 1 -- Monday: ..." label; the
    lookup must still find it via the shared "Day N" prefix instead of
    silently failing to badge a real swap."""
    import api.main as m
    from auth import ownership
    from tools import memory as tools_memory

    owner = _make_user("owner8")
    session_id = "s8"
    ownership.create_session(session_id, user_id=owner["id"], goal="hypertrophy")

    full_plan = """

## User Profile + Plan Header
Day 1 - hard: muscles [chest] | max_sets: 10 | intensity: hard

---

## chest - hard
1. Flat Barbell Bench Press 4x8 | Rest 2-3 min | RPE 8
   -> heavy compound pressing.
2. Cable Fly 3x12 | Rest 90s | RPE 7
   -> isolation.

Evidence: compound presses prioritized.

---

## Weekly Schedule
### Day 1 -- Monday: Push (Chest) - Hard Session
**Warm-up:** Dynamic shoulder circles.

| # | Exercise | Sets x Reps | Rest | RPE |
|---|----------|-------------|------|-----|
| 1 | Flat Barbell Bench Press | 4x8 | 2-3 min | 8 |
| 2 | Cable Fly | 3x12 | 90s | 7 |

**Coaching notes:** Focus on controlled eccentrics.
"""
    session_dir = os.path.join(tools_memory.SESSION_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    with open(os.path.join(session_dir, "plan.md"), "w", encoding="utf-8") as f:
        f.write(full_plan)

    get_plan_adjustments_table().put_item(Item={
        "adjustment_id": str(uuid.uuid4()),
        "session_day_key": f"{session_id}#Day 1",
        "session_id": session_id, "day_label": "Day 1",
        "exercise_name": "Cable Fly", "new_exercise_name": "Machine Chest Press",
        "sets": None, "reps": None, "rpe": None,
        "reason": "Reported shoulder pain on Cable Fly",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    client = TestClient(m.app)
    token = tokens.create_access_token(user_id=owner["id"])
    r = client.get(f"/sessions/{session_id}/plan", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    day1 = body["days"][0]
    exercises_by_name = {e["name"]: e for e in day1["exercises"]}
    swapped = exercises_by_name["Machine Chest Press"]
    assert swapped["replaced_from"] == "Cable Fly"
    assert swapped["adjustment_reason"] == "Reported shoulder pain on Cable Fly"


def test_volume_only_adjustment_updates_sets_reps_rpe_without_replaced_from():
    """A too_hard/too_easy adjustment (prompts/plan_adjuster.md) never sets
    new_exercise_name — only sets/reps/rpe change, the exercise itself stays.
    The response must reflect the new sets/reps/rpe and carry the reason,
    but must NOT set replaced_from (nothing was renamed)."""
    import api.main as m
    from auth import ownership
    from tools import memory as tools_memory

    owner = _make_user("owner9")
    session_id = "s9"
    ownership.create_session(session_id, user_id=owner["id"], goal="hypertrophy")

    full_plan = """

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
"""
    session_dir = os.path.join(tools_memory.SESSION_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    with open(os.path.join(session_dir, "plan.md"), "w", encoding="utf-8") as f:
        f.write(full_plan)

    day_label = "Day 1 -- Monday: Push (Chest) - Hard Session"
    get_plan_adjustments_table().put_item(Item={
        "adjustment_id": str(uuid.uuid4()),
        "session_day_key": f"{session_id}#{day_label}",
        "session_id": session_id, "day_label": day_label,
        "exercise_name": "Flat Barbell Bench Press", "new_exercise_name": None,
        "sets": 3, "reps": None, "rpe": 7,
        "reason": "Too easy at 4 sets, dropped a set and RPE target",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    client = TestClient(m.app)
    token = tokens.create_access_token(user_id=owner["id"])
    r = client.get(f"/sessions/{session_id}/plan", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    exercise = body["days"][0]["exercises"][0]
    assert exercise["name"] == "Flat Barbell Bench Press"
    assert exercise["replaced_from"] is None
    assert exercise["sets"] == 3
    assert exercise["reps"] == "8"
    assert exercise["rpe"] == "7"
    assert exercise["adjustment_reason"] == "Too easy at 4 sets, dropped a set and RPE target"


def test_pending_response_has_no_days():
    import api.main as m

    owner = _make_user("owner6")
    ownership.create_session("s6", user_id=owner["id"], goal="hypertrophy")

    client = TestClient(m.app)
    token = tokens.create_access_token(user_id=owner["id"])
    r = client.get("/sessions/s6/plan", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["days"] is None


def test_ready_when_schedule_has_been_written():
    import api.main as m

    owner = _make_user("owner3")
    session_id = "s3"
    ownership.create_session(session_id, user_id=owner["id"], goal="hypertrophy")
    tools_memory.write_plan_memory.invoke({
        "session_id": session_id,
        "section_title": "Weekly Schedule",
        "content": "### Day 1 — Push\n| # | Exercise | Sets x Reps | Rest | RPE |\n|---|---|---|---|---|\n| 1 | Bench Press | 4x8 | 2 min | 8 |",
    })

    client = TestClient(m.app)
    token = tokens.create_access_token(user_id=owner["id"])
    r = client.get(f"/sessions/{session_id}/plan", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert "Bench Press" in body["plan"]


def test_requires_auth():
    import api.main as m

    client = TestClient(m.app)
    r = client.get("/sessions/anything/plan")
    assert r.status_code == 401
