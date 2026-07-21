"""Tests for tools/rag/filtering.py. The filter-builder tests below are
pure (no I/O). The metadata-extractor tests (added in a later task) use a
fake LLM — this suite never makes a real LLM call, matching the rest of
this project's test suite."""

from tools.rag.filtering import GoalFilterBuilder, PrinciplesFilterBuilder
from tools.rag.models import GoalQueryFilter, PrinciplesQueryFilter


def test_goal_filter_builder_includes_all_sentinel_for_muscle_and_experience():
    query_filter = GoalQueryFilter(
        muscle=["chest"], experience_level="beginner", goals=["hypertrophy"],
    )
    built = GoalFilterBuilder().build(query_filter)

    conditions = {c.key: c.match.any for c in built.must}
    assert set(conditions["metadata.muscle"]) == {"chest", "all"}
    assert set(conditions["metadata.experience_level"]) == {"beginner", "all"}
    assert conditions["metadata.goals"] == ["hypertrophy"]
    assert "metadata.topic" not in conditions


def test_goal_filter_builder_empty_filter_has_no_conditions():
    built = GoalFilterBuilder().build(GoalQueryFilter())
    assert built.must == []


def test_principles_filter_builder_includes_all_sentinel_for_applies_to():
    query_filter = PrinciplesQueryFilter(applies_to=["hypertrophy"], topic=["volume"])
    built = PrinciplesFilterBuilder().build(query_filter)

    conditions = {c.key: c.match.any for c in built.must}
    assert set(conditions["metadata.applies_to"]) == {"hypertrophy", "all"}
    assert conditions["metadata.topic"] == ["volume"]


def test_principles_filter_builder_empty_filter_has_no_conditions():
    built = PrinciplesFilterBuilder().build(PrinciplesQueryFilter())
    assert built.must == []
