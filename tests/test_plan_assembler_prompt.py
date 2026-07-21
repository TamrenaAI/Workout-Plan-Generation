"""Confirms the plan_assembler prompt balances push/pull composition within
a single day, and frames BF%-related notes honestly (see Task 8) -- plain-text
assertions since the prompt is only ever consumed by an LLM, not by code."""

from config import load_prompt


def test_prompt_balances_push_pull_within_a_single_day():
    text = load_prompt("plan_assembler")
    assert "pressing-pattern exercises" in text
    assert "pulling-pattern exercises" in text


def test_prompt_frames_bf_notes_as_a_lean_not_an_outcome():
    text = load_prompt("plan_assembler")
    assert "NEVER framed as" in text
    assert "nutrition/energy-balance outcome" in text
