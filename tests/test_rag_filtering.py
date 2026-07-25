"""Tests for tools/rag/filtering.py. The filter-builder tests below are
pure (no I/O). The metadata-extractor tests (added in a later task) use a
fake LLM — this suite never makes a real LLM call, matching the rest of
this project's test suite."""

from tools.rag.filtering import GoalFilterBuilder, PrinciplesFilterBuilder
from tools.rag.models import GoalQueryFilter, PrinciplesQueryFilter


def test_goal_filter_builder_includes_all_sentinel_for_muscle_experience_and_goals():
    query_filter = GoalQueryFilter(
        muscle=["chest"], experience_level="beginner", goals=["hypertrophy"],
    )
    built = GoalFilterBuilder().build(query_filter)

    conditions = {c.key: c.match.any for c in built.must}
    assert set(conditions["metadata.muscle"]) == {"chest", "all"}
    assert set(conditions["metadata.experience_level"]) == {"beginner", "all"}
    # "all" must be included here too — real ingested data has goals=["all"]
    # on a majority of principles/strength docs (see tools/rag/models.py's
    # PrinciplesGoal/TrainingGoal Literal fix), so a goal-filtered search
    # that didn't also match "all" would silently exclude most of them.
    assert set(conditions["metadata.goals"]) == {"hypertrophy", "all"}
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


from langchain_core.runnables import RunnableLambda

from tools.rag.filtering import GoalMetadataExtractor, PrinciplesMetadataExtractor


class _FakeLLM:
    """Stands in for a real BaseChatModel — .with_structured_output(...)
    returns a Runnable that always yields a fixed value, so extractor
    tests never make a network call."""

    def __init__(self, value):
        self.value = value
        self.call_count = 0

    def with_structured_output(self, _schema):
        def _invoke(_prompt_value):
            self.call_count += 1
            return self.value

        return RunnableLambda(_invoke)


def test_goal_metadata_extractor_returns_structured_filter():
    expected = GoalQueryFilter(muscle=["chest"], goals=["hypertrophy"])
    fake_llm = _FakeLLM(expected)
    extractor = GoalMetadataExtractor(llm=fake_llm)

    result = extractor.extract("chest compound movements for hypertrophy")

    assert result == expected


def test_goal_metadata_extractor_caches_by_exact_query():
    fake_llm = _FakeLLM(GoalQueryFilter())
    extractor = GoalMetadataExtractor(llm=fake_llm)

    extractor.extract("same query")
    extractor.extract("same query")

    assert fake_llm.call_count == 1


def test_principles_metadata_extractor_returns_structured_filter():
    expected = PrinciplesQueryFilter(topic=["volume"], applies_to=["all"])
    fake_llm = _FakeLLM(expected)
    extractor = PrinciplesMetadataExtractor(llm=fake_llm)

    result = extractor.extract("general training volume guidance")

    assert result == expected


def test_principles_metadata_extractor_caches_by_exact_query():
    fake_llm = _FakeLLM(PrinciplesQueryFilter())
    extractor = PrinciplesMetadataExtractor(llm=fake_llm)

    extractor.extract("same query")
    extractor.extract("same query")

    assert fake_llm.call_count == 1
