"""Confirms the supervisor prompt tells the agent to give a stated priority
muscle extra weekly volume -- a plain-text assertion since the prompt is
only ever consumed by an LLM, not by code."""

from config import load_prompt


def test_prompt_instructs_targeting_top_of_range_for_priority_muscle():
    text = load_prompt("supervisor")
    assert "target the TOP of the range" in text
