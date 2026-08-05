"""Confirms the coach prompt tells the agent which tool to call for which
kind of question, and to never call a tool for unrelated questions -- a
plain-text assertion since the prompt is only ever consumed by an LLM, not
by code (same pattern as tests/test_supervisor_prompt.py)."""

from config import load_prompt


def test_prompt_instructs_workout_tool_for_training_questions():
    text = load_prompt("coach")
    assert "get_workout_history" in text


def test_prompt_instructs_nutrition_tool_for_food_questions():
    text = load_prompt("coach")
    assert "get_nutrition_plan" in text


def test_prompt_instructs_no_tool_calls_for_unrelated_questions():
    text = load_prompt("coach")
    assert "NEITHER tool" in text


def test_prompt_forbids_inventing_numbers_not_from_a_tool():
    text = load_prompt("coach")
    assert "Never state a specific number" in text
