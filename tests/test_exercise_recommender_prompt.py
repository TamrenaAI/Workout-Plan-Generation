"""Confirms the exercise_recommender prompt tells the agent to pass the
plan's paradigm as search_rag's goal argument — a plain-text assertion
since the prompt itself is only ever consumed by an LLM, not by code."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import load_prompt


def test_prompt_instructs_passing_goal_to_search_rag():
    text = load_prompt("exercise_recommender")
    assert "goal set to the plan's Paradigm value" in text
