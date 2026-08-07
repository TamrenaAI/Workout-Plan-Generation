"""Tests for agents/coach.py's tool closures. Never exercises
build_coach_agent()/the LLM itself -- same scoping as the rest of this
test suite (see tests/test_workout_feedback.py's docstring). DynamoDB
access is moto-mocked per-test (tests/conftest.py's autouse dynamo_tables
fixture); plan.md files are written directly under the real
config.SESSION_DIR using fresh uuid4 session ids, same approach as
tests/test_memory_plan_reads.py."""

import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.coach import build_coach_tools
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


def _tool(tools, name):
    return next(t for t in tools if t.name == name)


def test_get_workout_history_returns_latest_ready_plan():
    user_id = _uid()
    _make_ready_session(user_id, "## Weekly Schedule\n### Day 1\nSquat 3x5")
    tools = build_coach_tools(user_id, nutrition_snapshot=None)
    result = _tool(tools, "get_workout_history").invoke({})
    assert "Squat 3x5" in result


def test_get_workout_history_ignores_non_ready_sessions():
    user_id = _uid()
    generating_session = str(uuid.uuid4())
    ownership.create_session(generating_session, user_id=user_id, goal="hypertrophy")
    # left in "generating" status -- never marked ready, and no plan.md written

    tools = build_coach_tools(user_id, nutrition_snapshot=None)
    result = _tool(tools, "get_workout_history").invoke({})
    assert result == "(no workout plan yet)"


def test_get_workout_history_returns_placeholder_when_no_sessions_at_all():
    tools = build_coach_tools(_uid(), nutrition_snapshot=None)
    result = _tool(tools, "get_workout_history").invoke({})
    assert result == "(no workout plan yet)"


def test_get_workout_history_is_scoped_to_the_given_user():
    owner, other = _uid(), _uid()
    _make_ready_session(owner, "## Weekly Schedule\n### Day 1\nOwner's plan")

    tools = build_coach_tools(other, nutrition_snapshot=None)
    result = _tool(tools, "get_workout_history").invoke({})
    assert result == "(no workout plan yet)"


def test_get_nutrition_plan_returns_provided_snapshot():
    tools = build_coach_tools(_uid(), nutrition_snapshot='{"calories": 2200}')
    result = _tool(tools, "get_nutrition_plan").invoke({})
    assert result == '{"calories": 2200}'


def test_get_nutrition_plan_returns_placeholder_when_snapshot_is_none():
    tools = build_coach_tools(_uid(), nutrition_snapshot=None)
    result = _tool(tools, "get_nutrition_plan").invoke({})
    assert result == "(no nutrition plan yet)"
