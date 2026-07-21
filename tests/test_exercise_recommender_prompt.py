"""Confirms the exercise_recommender prompt tells the agent to pass the
plan's paradigm as search_rag's goal argument — a plain-text assertion
since the prompt itself is only ever consumed by an LLM, not by code."""

from config import load_prompt


def test_prompt_instructs_passing_goal_to_search_rag():
    text = load_prompt("exercise_recommender")
    assert "goal set to the plan's Paradigm value" in text


def test_prompt_prefers_regressed_variants_for_beginners_on_bodyweight_compounds():
    text = load_prompt("exercise_recommender")
    assert "assisted or regressed variant" in text


def test_prompt_splits_hypertrophy_reps_by_compound_vs_isolation():
    text = load_prompt("exercise_recommender")
    assert "Compound Reps" in text
    assert "Isolation Reps" in text


def test_prompt_gives_concrete_injury_guidance_under_any_paradigm():
    text = load_prompt("exercise_recommender")
    assert "Injury/limitation rule" in text
    assert "regardless of paradigm" in text
