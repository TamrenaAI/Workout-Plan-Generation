"""Tests for tools/rag/models.py — the Pydantic schemas matching the data
already ingested into rag_data/qdrant. No I/O, no external services."""

import pytest
from pydantic import ValidationError

from tools.rag.models import (
    Chunk,
    GoalNamespaceMetadata,
    GoalQueryFilter,
    PrinciplesMetadata,
    PrinciplesQueryFilter,
    ScoredChunk,
)


def test_chunk_accepts_valid_hypertrophy_metadata():
    chunk = Chunk(
        id="c1",
        text="some chunk text",
        book="book1",
        chapter="1",
        collection="hypertrophy",
        chunk_index=0,
        metadata=GoalNamespaceMetadata(
            muscle=["chest"],
            topic=["volume"],
            experience_level="beginner",
            goals=["hypertrophy"],
        ),
    )
    assert chunk.metadata.muscle == ["chest"]


def test_chunk_rejects_invalid_collection_literal():
    with pytest.raises(ValidationError):
        Chunk(
            id="c1",
            text="t",
            book="b",
            chapter="1",
            collection="not-a-real-collection",
            chunk_index=0,
            metadata=None,
        )


def test_scored_chunk_adds_score_field():
    chunk = ScoredChunk(
        id="c1",
        text="t",
        book="b",
        chapter="1",
        collection="principles",
        chunk_index=0,
        metadata=None,
        score=0.42,
    )
    assert chunk.score == 0.42


def test_goal_query_filter_defaults_to_all_none():
    query_filter = GoalQueryFilter()
    assert query_filter.muscle is None
    assert query_filter.topic is None
    assert query_filter.experience_level is None
    assert query_filter.goals is None


def test_principles_query_filter_defaults_to_all_none():
    query_filter = PrinciplesQueryFilter()
    assert query_filter.topic is None
    assert query_filter.planner_stage is None
    assert query_filter.applies_to is None


def test_principles_metadata_requires_all_fields():
    with pytest.raises(ValidationError):
        PrinciplesMetadata(topic=["volume"])
