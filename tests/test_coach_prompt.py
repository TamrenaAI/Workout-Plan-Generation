"""Confirms the coach prompt tells the agent which injected context section
to ground its answer in for which kind of question, and to ignore both for
unrelated questions -- a plain-text assertion since the prompt is only ever
consumed by an LLM, not by code (same pattern as
tests/test_supervisor_prompt.py). No tool-calling instructions here --
workout history and nutrition plan are always injected into the system
prompt already (see agents/coach.py's module docstring for why)."""

from config import load_prompt


def test_prompt_references_workout_plan_section_for_training_questions():
    text = load_prompt("coach")
    assert "Workout Plan" in text


def test_prompt_references_nutrition_plan_section_for_food_questions():
    text = load_prompt("coach")
    assert "Nutrition Plan" in text


def test_prompt_instructs_ignoring_both_sections_for_unrelated_questions():
    text = load_prompt("coach")
    assert "ignore both" in text


def test_prompt_forbids_inventing_numbers_not_from_a_tool():
    text = load_prompt("coach")
    assert "Never state a specific number" in text


def test_prompt_distinguishes_temporarily_unavailable_nutrition_plan():
    text = load_prompt("coach")
    assert "(nutrition plan temporarily unavailable)" in text
