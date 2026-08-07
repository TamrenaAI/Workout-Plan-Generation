"""Tests for agents/coach.py's context-gathering helpers. Never exercises
run_coach_turn()/the LLM itself -- same scoping as the rest of this test
suite (see tests/test_workout_feedback.py's docstring). DynamoDB access is
moto-mocked per-test (tests/conftest.py's autouse dynamo_tables fixture);
plan.md files are written directly under the real config.SESSION_DIR using
fresh uuid4 session ids, same approach as tests/test_memory_plan_reads.py.

Both "tools" (workout history, nutrition snapshot) are fetched eagerly and
injected into the system prompt rather than routed through an LLM
tool-calling loop -- see agents/coach.py's module docstring for why
(ITIBedrockChat has no bind_tools support)."""

import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.coach import _build_system_prompt, _get_workout_history
from auth import ownership
from config import SESSION_DIR


def _uid() -> str:
    return str(uuid.uuid4())


def _make_ready_session(user_id: str, schedule_content: str) -> str:
    session_id = str(uuid.uuid4())
    ownership.create_session(session_id, user_id=user_id, goal="hypertrophy")
    ownership.update_session_status(session_id, "ready")
    session_path = os.path.join(SESSION_DIR, session_id)
    os.makedirs(session_path, exist_ok=True)
    with open(os.path.join(session_path, "plan.md"), "w", encoding="utf-8") as f:
        f.write(schedule_content)
    return session_id


def test_get_workout_history_returns_latest_ready_plan():
    user_id = _uid()
    _make_ready_session(user_id, "## Weekly Schedule\n### Day 1\nSquat 3x5")
    result = _get_workout_history(user_id)
    assert "Squat 3x5" in result


def test_get_workout_history_ignores_non_ready_sessions():
    user_id = _uid()
    generating_session = str(uuid.uuid4())
    ownership.create_session(generating_session, user_id=user_id, goal="hypertrophy")
    # left in "generating" status -- never marked ready, and no plan.md written

    result = _get_workout_history(user_id)
    assert result == "(no workout plan yet)"


def test_get_workout_history_returns_placeholder_when_no_sessions_at_all():
    result = _get_workout_history(_uid())
    assert result == "(no workout plan yet)"


def test_get_workout_history_is_scoped_to_the_given_user():
    owner, other = _uid(), _uid()
    _make_ready_session(owner, "## Weekly Schedule\n### Day 1\nOwner's plan")

    result = _get_workout_history(other)
    assert result == "(no workout plan yet)"


def test_system_prompt_includes_provided_nutrition_snapshot():
    prompt = _build_system_prompt(_uid(), nutrition_snapshot='{"calories": 2200}')
    assert '{"calories": 2200}' in prompt


def test_system_prompt_uses_placeholder_when_snapshot_is_none():
    prompt = _build_system_prompt(_uid(), nutrition_snapshot=None)
    assert "(no nutrition plan yet)" in prompt


def test_system_prompt_includes_workout_history():
    user_id = _uid()
    _make_ready_session(user_id, "## Weekly Schedule\n### Day 1\nSquat 3x5")
    prompt = _build_system_prompt(user_id, nutrition_snapshot=None)
    assert "Squat 3x5" in prompt
