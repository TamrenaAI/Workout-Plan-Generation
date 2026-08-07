"""
Seed a ready-to-test plan session with a real workout routine written to
plan.md — no LLM call, no pipeline run required.

Both manual test targets need an existing session in a specific state that
the normal pipeline only produces after several agent calls:
  - POST /workouts/{session_id}/feedback needs a session whose plan.md
    already has real exercise names in it (see prompts/plan_adjuster.md
    step 1 — it reads plan memory first).
  - POST /plan/{session_id}/monthly-review needs status="ready" AND
    created_at at least 30 days in the past (see auth/ownership.py's
    _REVIEW_ELIGIBLE_AFTER_DAYS, tested in tests/test_review_eligibility.py).

This service no longer owns user identity (see
docs/superpowers/specs/2026-07-25-bff-auth-handoff-design.md), so this
script does not create or persist a user record — it generates a random
uuid4 to use as the user_id and creates a session backdated 31 days and
marked ready, with a plan.md written in the same DAY MAP + muscle-group
+ Weekly Schedule format the real pipeline produces (see
sessions/6f3c6194-c99e-4a3d-bbcc-6d8296103fff/plan.md for reference).

Usage:
    python scripts/seed_test_session.py
"""

import argparse
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from auth import ownership
from auth.tokens import create_access_token
from tools.dynamo import get_plan_sessions_table
from tools.memory import write_plan_memory

_INTAKE = {
    "goal": "hypertrophy", "days_per_week": 3, "experience": "intermediate",
    "session_duration": "45min", "injuries": None, "priority": "chest",
    "age": 30, "sleep_quality": None, "job_type": None, "current_program": None,
}

_HEADER = """User Profile:
- Goal: hypertrophy
- Days per week: 3
- Experience: intermediate
- Session duration: 45min
- Priority focus: chest

Training Plan Decisions:
- Paradigm: hypertrophy
- Split: Full Body x3
- Muscle groups: chest, back, shoulders, arms, legs
- Intensity zone: medium for all days
- Weekly volume: 14-18 sets per muscle group"""

_DAY_MAP = """Day 1 - medium: muscles [chest, back, shoulders, arms, legs] | max_sets: 10 | intensity: medium
Day 2 - medium: muscles [chest, back, shoulders, arms, legs] | max_sets: 10 | intensity: medium
Day 3 - medium: muscles [chest, back, shoulders, arms, legs] | max_sets: 10 | intensity: medium"""

_CHEST = """1. Flat Barbell Bench Press 4x10-12 | Rest 90s | RPE 7
2. Incline Dumbbell Press 3x10-12 | Rest 90s | RPE 7
3. Cable Fly 3x10-12 | Rest 90s | RPE 7"""

_BACK = """1. Pull-Up 4x10-12 | Rest 90s | RPE 7
2. Single-Arm Dumbbell Row 3x10-12 | Rest 90s | RPE 7
3. Lat Pulldown 3x10-12 | Rest 90s | RPE 7"""

_SHOULDERS = """1. Barbell Overhead Press 4x10-12 | Rest 90s | RPE 7
2. Dumbbell Lateral Raise 3x10-12 | Rest 90s | RPE 7"""

_ARMS = """1. Close-Grip Bench Press 4x10-12 | Rest 90s | RPE 7
2. Hammer Curl 3x10-12 | Rest 90s | RPE 7"""

_LEGS = """1. Barbell Back Squat 4x10-12 | Rest 90s | RPE 7
2. Leg Press 3x10-12 | Rest 90s | RPE 7
3. Romanian Deadlift 3x10-12 | Rest 90s | RPE 7"""

_WEEKLY_SCHEDULE = """### Day 1 — Monday: Full Body Focus with Chest Emphasis
| # | Exercise | Sets × Reps | Rest | RPE |
|---|----------|-------------|------|-----|
| 1 | Flat Barbell Bench Press | 4×10-12 | 90s | 7 |
| 2 | Pull-Up | 4×10-12 | 90s | 7 |
| 3 | Barbell Overhead Press | 4×10-12 | 90s | 7 |
| 4 | Barbell Back Squat | 4×10-12 | 90s | 7 |
| 5 | Close-Grip Bench Press | 4×10-12 | 90s | 7 |

---

### Day 2 — Wednesday: Full Body Balanced Volume
| # | Exercise | Sets × Reps | Rest | RPE |
|---|----------|-------------|------|-----|
| 1 | Incline Dumbbell Press | 3×10-12 | 90s | 7 |
| 2 | Single-Arm Dumbbell Row | 3×10-12 | 90s | 7 |
| 3 | Dumbbell Lateral Raise | 3×10-12 | 90s | 7 |
| 4 | Leg Press | 3×10-12 | 90s | 7 |
| 5 | Hammer Curl | 3×10-12 | 90s | 7 |

---

### Day 3 — Friday: Full Body Volume and Isolation Focus
| # | Exercise | Sets × Reps | Rest | RPE |
|---|----------|-------------|------|-----|
| 1 | Cable Fly | 3×10-12 | 90s | 7 |
| 2 | Lat Pulldown | 3×10-12 | 90s | 7 |
| 3 | Romanian Deadlift | 3×10-12 | 90s | 7 |"""


def seed() -> str:
    # See tests/test_corrective.py's _make_user for why this no longer
    # calls into auth.models — this service doesn't own `users` anymore.
    user_id = str(uuid.uuid4())

    session_id = str(uuid.uuid4())

    ownership.create_session(session_id, user_id, "hypertrophy", intake=_INTAKE)

    write_plan_memory.invoke({
        "session_id": session_id,
        "section_title": "Session Header and Training Plan Decisions",
        "content": _HEADER,
    })
    write_plan_memory.invoke({"session_id": session_id, "section_title": "DAY MAP", "content": _DAY_MAP})
    write_plan_memory.invoke({"session_id": session_id, "section_title": "chest - medium", "content": _CHEST})
    write_plan_memory.invoke({"session_id": session_id, "section_title": "back - medium", "content": _BACK})
    write_plan_memory.invoke({"session_id": session_id, "section_title": "shoulders - medium", "content": _SHOULDERS})
    write_plan_memory.invoke({"session_id": session_id, "section_title": "arms - medium", "content": _ARMS})
    write_plan_memory.invoke({"session_id": session_id, "section_title": "legs - medium", "content": _LEGS})
    write_plan_memory.invoke({
        "session_id": session_id,
        "section_title": "Weekly Schedule",
        "content": _WEEKLY_SCHEDULE,
    })

    # Backdate + mark ready so this session is immediately eligible for a
    # monthly review (>= 30 days old, status ready — see auth/ownership.py).
    # auth.ownership.update_session_status() doesn't expose backdating
    # created_at, so this dev script updates the item directly — matching
    # the UpdateExpression pattern in auth/ownership.py::update_session_status.
    backdated = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    get_plan_sessions_table().update_item(
        Key={"session_id": session_id},
        UpdateExpression="SET #s = :status, created_at = :created_at",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":status": "ready", ":created_at": backdated},
    )

    return session_id, user_id


def main():
    parser = argparse.ArgumentParser(description="Seed a ready-to-test plan session with a real workout routine.")
    parser.parse_args()

    session_id, user_id = seed()
    token = create_access_token(user_id=user_id)

    print("Seeded session ready for testing.\n")
    print(f"  session_id : {session_id}")
    print(f"  user_id    : {user_id}")
    print(f"  plan.md    : sessions/{session_id}/plan.md")
    print(f"  bearer     : {token}\n")

    print("Test feedback (triggers Plan Adjuster — flags Flat Barbell Bench Press as too_hard):")
    print(f"""  curl -X POST http://localhost:8000/workouts/{session_id}/feedback \\
    -H "Authorization: Bearer {token}" -H "Content-Type: application/json" \\
    -d '{{"day_label": "Day 1", "exercises": [{{"name": "Flat Barbell Bench Press", "difficulty": "too_hard", "pain": false}}]}}'
""")

    print("Test monthly review (session is already 31 days old and status=ready, so eligible_for_review=True):")
    print(f"""  curl -X POST http://localhost:8000/plan/{session_id}/monthly-review \\
    -H "Authorization: Bearer {token}" \\
    -F "same_goal=true" -F "inbody_file=@/path/to/inbody.jpg"
""")


if __name__ == "__main__":
    main()
