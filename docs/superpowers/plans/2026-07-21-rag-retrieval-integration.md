# RAG Retrieval Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `tools/rag.py`'s hardcoded static stub with the real hybrid-search + reranking pipeline (bge-m3 dense + BM25 sparse + RRF fusion + bge-reranker-v2-m3), routed by training paradigm to the matching Qdrant collection and narrowed with LLM-extracted metadata filters, retrieving 10 chunks per collection and returning the top 3 after reranking.

**Architecture:** `tools/rag.py` becomes the `tools/rag/` package: `models.py` (Pydantic schemas matching the already-ingested `rag_data/qdrant` data), `filtering.py` (LLM-based metadata extraction + Qdrant filter building, one path for goal-specific collections and one for `principles`), `retrieval.py` (dense+sparse hybrid search per collection), `reranking.py` (cross-encoder reranking), and `pipeline.py` (orchestration: routes by `goal`, merges candidates, reranks, formats). `__init__.py` re-exports `search_rag` so `agents/exercise_recommender.py`'s `from tools.rag import search_rag` never changes.

**Tech Stack:** `qdrant-client` (local persisted mode), `sentence-transformers` (bge-m3 dense embeddings + bge-reranker-v2-m3 cross-encoder), `fastembed` (BM25 sparse embeddings), `langchain_core` (structured-output LLM extraction, `@tool` decorator), `pydantic` (schemas).

## Global Constraints

- Metadata-extraction LLM calls use `get_llm(temperature=0)` from `agents/llm.py` — Azure OpenAI is this project's only LLM provider; do not use the notebook's multi-provider `create_llm`.
- Per-collection hybrid retrieval: `top_k=10` (the RRF fusion `limit`).
- Final result count returned to the calling agent: top 3, after reranking the *merged* candidates across all collections queried.
- Collection routing by `goal`: `"hypertrophy"` → `[hypertrophy, principles]`; `"strength"` → `[strength, principles]`; anything else (including empty/unrecognized) → `[principles]`. Never an error.
- Embedding/reranker models cache under `data/models/` (already gitignored via the existing `data/` rule in `.gitignore`) — not the notebook's `assets/` path.
- Qdrant points at the real committed data: `rag_data/qdrant`.
- No silent fallback to the old static stub on load failure — Qdrant/model load errors raise.
- `search_rag`'s contract (`from tools.rag import search_rag`, a `@tool`-decorated function) must keep working at every task boundary — the full test suite (`pytest tests/ -q`) must pass after every task, not just the new tests.

---

### Task 1: Relocate the stub into a package + add data models + pin dependencies

**Files:**
- Move: `tools/rag.py` → `tools/rag/__init__.py` (content unchanged)
- Create: `tools/rag/models.py`
- Create: `tests/test_rag_models.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `tools.rag.models.Chunk`, `tools.rag.models.ScoredChunk`, `tools.rag.models.GoalNamespaceMetadata`, `tools.rag.models.PrinciplesMetadata`, `tools.rag.models.GoalQueryFilter`, `tools.rag.models.PrinciplesQueryFilter` — Pydantic models every later task imports.

This task only relocates the existing stub (so `tools/rag/` becomes a package without changing behavior) and adds the schema layer nothing else depends on yet. `tools/rag/__init__.py` keeps returning the old static text until Task 6 rewires it — this keeps `agents/exercise_recommender.py`'s import working, and the full test suite green, at every commit in between.

- [ ] **Step 1: Relocate the stub file into a package**

```bash
git mv tools/rag.py tools/rag/__init__.py
```

- [ ] **Step 2: Verify nothing broke**

Run: `pytest tests/test_dev_login.py tests/test_workout_feedback.py tests/test_session_ownership.py tests/test_session_plan.py -q`
Expected: PASS (same as before the move — these are the tests that import `api.main`, which transitively imports `agents.exercise_recommender`, which does `from tools.rag import search_rag`).

- [ ] **Step 3: Pin the new dependencies in `requirements.txt`**

Replace this block:

```
# Exercise database is SQLite (stdlib sqlite3) at this stage — no MongoDB
# driver needed yet. RAG is a hardcoded stub (tools/rag.py) — no Qdrant /
# sentence-transformers / pinecone-text dependency yet either.
#
# Dev/notebook-only extras (ipykernel, ipywidgets, ...) are in
# requirements-dev.txt, not here.
```

with:

```
# Exercise database is SQLite (stdlib sqlite3) at this stage — no MongoDB
# driver needed yet.
#
# Dev/notebook-only extras (ipykernel, ipywidgets, ...) are in
# requirements-dev.txt, not here.

# ── RAG retrieval (tools/rag/) ────────────────────────────────
qdrant-client==1.14.3
sentence-transformers==4.0.1
fastembed==0.7.1
```

- [ ] **Step 4: Write the failing test for the data models**

Create `tests/test_rag_models.py`:

```python
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
```

- [ ] **Step 5: Run the test to verify it fails**

Run: `pytest tests/test_rag_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.rag.models'`

- [ ] **Step 6: Create `tools/rag/models.py`**

```python
"""
Pydantic models for RAG chunks and metadata, matching the data already
ingested into rag_data/qdrant by notebooks/chunking.ipynb +
notebooks/vectordb_retrieval.ipynb. Do not change field names or literal
values here without re-ingesting — this schema must match the stored
payloads exactly.
"""

from typing import Literal

from pydantic import BaseModel, Field


class PrinciplesMetadata(BaseModel):
    topic: list[
        Literal[
            "program_design", "periodization", "progressive_overload", "volume",
            "frequency", "intensity", "load", "exercise_selection", "recovery",
            "fatigue", "warmup", "energy_systems",
        ]
    ] = Field(min_length=1)

    planner_stage: list[
        Literal[
            "goal_selection", "program_design", "exercise_selection",
            "progression", "recovery",
        ]
    ] = Field(min_length=1)

    goals: list[
        Literal["hypertrophy", "strength", "fat_loss", "endurance"]
    ] = Field(min_length=1)

    applies_to: list[
        Literal["all", "hypertrophy", "strength", "fat_loss"]
    ] = Field(min_length=1)

    knowledge_type: list[
        Literal["definition", "principle", "recommendation", "warning", "protocol"]
    ] = Field(min_length=1)


class GoalNamespaceMetadata(BaseModel):
    muscle: list[
        Literal[
            "all", "chest", "back", "shoulders", "biceps", "triceps", "forearms",
            "quads", "hamstrings", "glutes", "calves", "abs",
        ]
    ] = Field(min_length=1)

    topic: list[
        Literal[
            "muscle_physiology", "neuromuscular_system", "muscle_activation",
            "biomechanics", "muscle_growth_mechanisms", "hypertrophy_programming",
            "maximal_strength", "force_production", "power_development",
            "neural_adaptation", "volume", "frequency", "intensity", "load",
            "exercise_selection", "exercise_order", "periodization", "recovery",
            "fatigue_management", "advanced_techniques",
        ]
    ] = Field(min_length=1)

    experience_level: Literal["all", "beginner", "intermediate", "advanced"]

    goals: list[
        Literal["hypertrophy", "strength", "fat_loss"]
    ] = Field(min_length=1)


class Chunk(BaseModel):
    id: str
    text: str
    book: str
    chapter: str
    collection: Literal["principles", "hypertrophy", "strength"]
    chunk_index: int
    metadata: PrinciplesMetadata | GoalNamespaceMetadata | None = None


class ScoredChunk(Chunk):
    score: float


class PrinciplesQueryFilter(BaseModel):
    topic: list[
        Literal[
            "program_design", "periodization", "progressive_overload", "volume",
            "frequency", "intensity", "load", "exercise_selection", "recovery",
            "fatigue", "warmup", "energy_systems",
        ]
    ] | None = None

    planner_stage: list[
        Literal[
            "goal_selection", "program_design", "exercise_selection",
            "progression", "recovery",
        ]
    ] | None = None

    goals: list[
        Literal["hypertrophy", "strength", "fat_loss", "endurance"]
    ] | None = None

    applies_to: list[
        Literal["all", "hypertrophy", "strength", "fat_loss"]
    ] | None = None

    knowledge_type: list[
        Literal["definition", "principle", "recommendation", "warning", "protocol"]
    ] | None = None


class GoalQueryFilter(BaseModel):
    muscle: list[
        Literal[
            "all", "chest", "back", "shoulders", "biceps", "triceps", "forearms",
            "quads", "hamstrings", "glutes", "calves", "abs",
        ]
    ] | None = None

    topic: list[
        Literal[
            "muscle_physiology", "neuromuscular_system", "muscle_activation",
            "biomechanics", "muscle_growth_mechanisms", "hypertrophy_programming",
            "maximal_strength", "force_production", "power_development",
            "neural_adaptation", "volume", "frequency", "intensity", "load",
            "exercise_selection", "exercise_order", "periodization", "recovery",
            "fatigue_management", "advanced_techniques",
        ]
    ] | None = None

    experience_level: Literal["all", "beginner", "intermediate", "advanced"] | None = None

    goals: list[
        Literal["hypertrophy", "strength", "fat_loss"]
    ] | None = None
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `pytest tests/test_rag_models.py -v`
Expected: PASS (6 tests)

- [ ] **Step 8: Commit**

```bash
git add tools/rag/__init__.py tools/rag/models.py tests/test_rag_models.py requirements.txt
git commit -m "$(cat <<'EOF'
Relocate tools/rag.py into a package and add RAG data models

First step of replacing the static RAG stub with real retrieval — the
stub itself is unchanged (just moved), so search_rag's contract keeps
working while the real pipeline is built alongside it.
EOF
)"
```

---

### Task 2: Metadata filter builders (pure, no LLM/network)

**Files:**
- Create: `tools/rag/filtering.py` (this task writes the `BaseFilterBuilder`/`GoalFilterBuilder`/`PrinciplesFilterBuilder` half; Task 3 extends the same file)
- Create: `tests/test_rag_filtering.py` (this task writes the builder tests; Task 3 extends the same file)

**Interfaces:**
- Consumes: `tools.rag.models.GoalQueryFilter`, `tools.rag.models.PrinciplesQueryFilter` (Task 1)
- Produces: `tools.rag.filtering.BaseFilterBuilder`, `tools.rag.filtering.GoalFilterBuilder`, `tools.rag.filtering.PrinciplesFilterBuilder` — each with `.build(query_filter) -> qdrant_client.models.Filter`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_rag_filtering.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_rag_filtering.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.rag.filtering'`

- [ ] **Step 3: Create `tools/rag/filtering.py` (builders only)**

```python
"""
Turns an extracted query filter into a Qdrant Filter, and (see the
extractor classes added below) turns a raw query into that extracted
filter via an LLM structured-output call.

GoalFilterBuilder / GoalQueryFilter cover the hypertrophy/strength
collections (GoalNamespaceMetadata: muscle, topic, experience_level,
goals). PrinciplesFilterBuilder / PrinciplesQueryFilter cover the
principles collection (PrinciplesMetadata: topic, planner_stage, goals,
applies_to, knowledge_type) — a different schema, so a separate builder.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from qdrant_client.models import FieldCondition, Filter, MatchAny

from tools.rag.models import GoalQueryFilter, PrinciplesQueryFilter

T = TypeVar("T")


class BaseFilterBuilder(ABC, Generic[T]):
    @abstractmethod
    def build(self, query_filter: T) -> Filter:
        pass


class GoalFilterBuilder(BaseFilterBuilder[GoalQueryFilter]):
    def build(self, query_filter: GoalQueryFilter) -> Filter:
        must = []

        if query_filter.muscle:
            must.append(
                FieldCondition(
                    key="metadata.muscle",
                    match=MatchAny(any=[*query_filter.muscle, "all"]),
                )
            )

        if query_filter.topic:
            must.append(
                FieldCondition(
                    key="metadata.topic",
                    match=MatchAny(any=query_filter.topic),
                )
            )

        if query_filter.experience_level:
            must.append(
                FieldCondition(
                    key="metadata.experience_level",
                    match=MatchAny(any=[query_filter.experience_level, "all"]),
                )
            )

        if query_filter.goals:
            must.append(
                FieldCondition(
                    key="metadata.goals",
                    match=MatchAny(any=query_filter.goals),
                )
            )

        return Filter(must=must)


class PrinciplesFilterBuilder(BaseFilterBuilder[PrinciplesQueryFilter]):
    def build(self, query_filter: PrinciplesQueryFilter) -> Filter:
        must = []

        if query_filter.topic:
            must.append(
                FieldCondition(
                    key="metadata.topic",
                    match=MatchAny(any=query_filter.topic),
                )
            )

        if query_filter.planner_stage:
            must.append(
                FieldCondition(
                    key="metadata.planner_stage",
                    match=MatchAny(any=query_filter.planner_stage),
                )
            )

        if query_filter.goals:
            must.append(
                FieldCondition(
                    key="metadata.goals",
                    match=MatchAny(any=query_filter.goals),
                )
            )

        if query_filter.applies_to:
            must.append(
                FieldCondition(
                    key="metadata.applies_to",
                    match=MatchAny(any=[*query_filter.applies_to, "all"]),
                )
            )

        if query_filter.knowledge_type:
            must.append(
                FieldCondition(
                    key="metadata.knowledge_type",
                    match=MatchAny(any=query_filter.knowledge_type),
                )
            )

        return Filter(must=must)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_rag_filtering.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add tools/rag/filtering.py tests/test_rag_filtering.py
git commit -m "$(cat <<'EOF'
Add Qdrant filter builders for goal and principles metadata

Pure logic, no LLM/network — turns an extracted GoalQueryFilter or
PrinciplesQueryFilter into the qdrant_client Filter used to narrow a
collection search instead of scanning the whole collection.
EOF
)"
```

---

### Task 3: Metadata extractors (LLM structured-output, tested with a fake LLM)

**Files:**
- Modify: `tools/rag/filtering.py` (append extractor classes + prompts)
- Modify: `tests/test_rag_filtering.py` (append extractor tests)

**Interfaces:**
- Consumes: `tools.rag.models.GoalQueryFilter`, `tools.rag.models.PrinciplesQueryFilter` (Task 1); `langchain_core.language_models.BaseChatModel`
- Produces: `tools.rag.filtering.BaseMetadataExtractor`, `tools.rag.filtering.GoalMetadataExtractor`, `tools.rag.filtering.PrinciplesMetadataExtractor` — each constructed with `llm: BaseChatModel`, exposing `.extract(query: str) -> GoalQueryFilter | PrinciplesQueryFilter`, cached per exact query string.

No real LLM call is made in this test suite — a fake `BaseChatModel`-shaped object stands in, matching this project's existing convention of never exercising live LLM calls in `tests/` (see `tests/test_workout_feedback.py`'s module docstring).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_rag_filtering.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_rag_filtering.py -v`
Expected: FAIL with `ImportError: cannot import name 'GoalMetadataExtractor' from 'tools.rag.filtering'`

- [ ] **Step 3: Append the extractor classes and prompts to `tools/rag/filtering.py`**

Add these imports to the top of `tools/rag/filtering.py` (alongside the existing ones):

```python
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
```

Append to the end of `tools/rag/filtering.py`:

```python
class BaseMetadataExtractor(ABC, Generic[T]):
    @abstractmethod
    def extract(self, query: str) -> T:
        pass


GOAL_QUERY_FILTER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are an expert in exercise science.

Your task is to extract structured retrieval filters from a user's query.

The output will be used to filter a vector database before retrieval.

Guidelines:

1. Understand the semantic meaning of the query, not just the exact words.
2. Infer metadata when it is strongly implied by the user's intent.
3. Never guess. If you are not confident about a field, leave it empty.
4. Only extract metadata that is useful for retrieval.
5. Do not force every field to be populated.
6. Do not infer metadata solely from common associations. For example,
   "bench press" does not automatically imply "chest" unless the query is
   actually about training the chest.
7. Use "all" only when the user explicitly refers to everyone or to
   general recommendations.
8. Ignore conversational text that does not affect retrieval.
9. Return only the structured output.
            """,
        ),
        ("human", "User Query:\n\n{query}"),
    ]
)


class GoalMetadataExtractor(BaseMetadataExtractor[GoalQueryFilter]):
    def __init__(self, llm: BaseChatModel):
        self.chain = GOAL_QUERY_FILTER_PROMPT | llm.with_structured_output(GoalQueryFilter)
        self._cache: dict[str, GoalQueryFilter] = {}

    def extract(self, query: str) -> GoalQueryFilter:
        if query in self._cache:
            return self._cache[query]

        metadata = self.chain.invoke({"query": query})
        self._cache[query] = metadata
        return metadata


PRINCIPLES_QUERY_FILTER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are an expert in exercise science and program design.

Your task is to extract structured retrieval filters from a user's query
about general training principles (not muscle-specific guidance).

The output will be used to filter a vector database before retrieval.

Guidelines:

1. Understand the semantic meaning of the query, not just the exact words.
2. Infer metadata when it is strongly implied by the user's intent.
3. Never guess. If you are not confident about a field, leave it empty.
4. Only extract metadata that is useful for retrieval.
5. Do not force every field to be populated.
6. Use "all" in applies_to only when the query is about general
   recommendations that apply regardless of training goal.
7. Ignore conversational text that does not affect retrieval.
8. Return only the structured output.
            """,
        ),
        ("human", "User Query:\n\n{query}"),
    ]
)


class PrinciplesMetadataExtractor(BaseMetadataExtractor[PrinciplesQueryFilter]):
    def __init__(self, llm: BaseChatModel):
        self.chain = PRINCIPLES_QUERY_FILTER_PROMPT | llm.with_structured_output(PrinciplesQueryFilter)
        self._cache: dict[str, PrinciplesQueryFilter] = {}

    def extract(self, query: str) -> PrinciplesQueryFilter:
        if query in self._cache:
            return self._cache[query]

        metadata = self.chain.invoke({"query": query})
        self._cache[query] = metadata
        return metadata
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_rag_filtering.py -v`
Expected: PASS (8 tests total — 4 from Task 2 + 4 new)

- [ ] **Step 5: Commit**

```bash
git add tools/rag/filtering.py tests/test_rag_filtering.py
git commit -m "$(cat <<'EOF'
Add LLM-based metadata extractors for goal and principles queries

GoalMetadataExtractor / PrinciplesMetadataExtractor turn a raw search_rag
query into a structured filter (cached per exact query string) so
retrieval can narrow to a slice of a collection instead of scanning all
of it. Tested with a fake LLM — no real model call in this suite.
EOF
)"
```

---

### Task 4: Hybrid retrieval (dense + sparse RRF fusion per collection)

**Files:**
- Create: `tools/rag/retrieval.py`
- Create: `tests/test_rag_retrieval.py`

**Interfaces:**
- Consumes: `tools.rag.models.ScoredChunk` (Task 1)
- Produces: `tools.rag.retrieval.embed_dense_query`, `tools.rag.retrieval.embed_sparse_query`, `tools.rag.retrieval.hybrid_search`, `tools.rag.retrieval.BaseRetriever`, `tools.rag.retrieval.HybridRetriever` — `HybridRetriever(client, collection_name, dense_model, sparse_model, top_k=10).retrieve(query, query_filter=None) -> list[ScoredChunk]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_rag_retrieval.py`:

```python
"""Tests for tools/rag/retrieval.py. Uses fake dense/sparse models and a
fake Qdrant client — no real bge-m3, BM25, or Qdrant connection, matching
this project's convention of not exercising real external services in
tests/."""

import numpy as np

from tools.rag.retrieval import HybridRetriever, embed_dense_query, embed_sparse_query


class _FakeDenseModel:
    def encode(self, query, normalize_embeddings=True, convert_to_numpy=True):
        return np.array([0.1, 0.2, 0.3])


class _FakeSparseEmbedding:
    def __init__(self, indices, values):
        self.indices = np.array(indices)
        self.values = np.array(values)


class _FakeSparseModel:
    def embed(self, texts):
        return [_FakeSparseEmbedding([1, 5], [0.5, 0.3]) for _ in texts]


class _FakePoint:
    def __init__(self, payload, score):
        self.payload = payload
        self.score = score


class _FakeQueryResponse:
    def __init__(self, points):
        self.points = points


class _FakeQdrantClient:
    def __init__(self, response):
        self._response = response
        self.last_call_kwargs = None

    def query_points(self, **kwargs):
        self.last_call_kwargs = kwargs
        return self._response


def test_embed_dense_query_returns_a_plain_list():
    vector = embed_dense_query("chest exercises", _FakeDenseModel())
    assert vector == [0.1, 0.2, 0.3]


def test_embed_sparse_query_converts_to_sparse_vector():
    sparse_vector = embed_sparse_query("chest exercises", _FakeSparseModel())
    assert sparse_vector.indices == [1, 5]
    assert sparse_vector.values == [0.5, 0.3]


def test_hybrid_retriever_builds_scored_chunks_from_qdrant_points():
    payload = {
        "id": "c1",
        "text": "chest chunk",
        "book": "book1",
        "chapter": "1",
        "chunk_index": 0,
        "metadata": None,
    }
    response = _FakeQueryResponse(points=[_FakePoint(payload=payload, score=0.77)])
    client = _FakeQdrantClient(response)

    retriever = HybridRetriever(
        client=client,
        collection_name="hypertrophy",
        dense_model=_FakeDenseModel(),
        sparse_model=_FakeSparseModel(),
        top_k=10,
    )

    results = retriever.retrieve(query="chest exercises")

    assert len(results) == 1
    assert results[0].id == "c1"
    assert results[0].collection == "hypertrophy"
    assert results[0].score == 0.77
    assert client.last_call_kwargs["collection_name"] == "hypertrophy"
    assert client.last_call_kwargs["limit"] == 10


def test_hybrid_retriever_returns_empty_list_when_no_points():
    response = _FakeQueryResponse(points=[])
    client = _FakeQdrantClient(response)

    retriever = HybridRetriever(
        client=client,
        collection_name="principles",
        dense_model=_FakeDenseModel(),
        sparse_model=_FakeSparseModel(),
    )

    assert retriever.retrieve(query="anything") == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_rag_retrieval.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.rag.retrieval'`

- [ ] **Step 3: Create `tools/rag/retrieval.py`**

```python
"""
Hybrid (dense + sparse, RRF-fused) retrieval against a single Qdrant
collection. dense_model/sparse_model/client are injected rather than
constructed here — model/connection lifecycle belongs to
tools/rag/pipeline.py, not this module, so this stays trivially testable
with fakes.
"""

from abc import ABC, abstractmethod

from fastembed import SparseTextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, Fusion, FusionQuery, Prefetch, SparseVector
from sentence_transformers import SentenceTransformer

from tools.rag.models import ScoredChunk


def embed_dense_query(query: str, model: SentenceTransformer) -> list[float]:
    return model.encode(
        query,
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).tolist()


def embed_sparse_query(query: str, model: SparseTextEmbedding) -> SparseVector:
    sparse = list(model.embed([query]))[0]
    return SparseVector(
        indices=sparse.indices.tolist(),
        values=sparse.values.tolist(),
    )


def hybrid_search(
    client: QdrantClient,
    collection_name: str,
    query: str,
    dense_model: SentenceTransformer,
    sparse_model: SparseTextEmbedding,
    top_k: int = 10,
    query_filter: Filter | None = None,
):
    dense_vector = embed_dense_query(query=query, model=dense_model)
    sparse_vector = embed_sparse_query(query=query, model=sparse_model)

    return client.query_points(
        collection_name=collection_name,
        prefetch=[
            Prefetch(using="dense", query=dense_vector, limit=top_k),
            Prefetch(using="sparse", query=sparse_vector, limit=top_k),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        query_filter=query_filter,
        limit=top_k,
        with_payload=True,
    )


class BaseRetriever(ABC):
    @abstractmethod
    def retrieve(self, query: str, query_filter: Filter | None = None) -> list[ScoredChunk]:
        pass


class HybridRetriever(BaseRetriever):
    def __init__(
        self,
        client: QdrantClient,
        collection_name: str,
        dense_model: SentenceTransformer,
        sparse_model: SparseTextEmbedding,
        top_k: int = 10,
    ):
        self.client = client
        self.collection_name = collection_name
        self.dense_model = dense_model
        self.sparse_model = sparse_model
        self.top_k = top_k

    def retrieve(self, query: str, query_filter: Filter | None = None) -> list[ScoredChunk]:
        results = hybrid_search(
            client=self.client,
            collection_name=self.collection_name,
            query=query,
            dense_model=self.dense_model,
            sparse_model=self.sparse_model,
            top_k=self.top_k,
            query_filter=query_filter,
        )

        return [
            ScoredChunk(**point.payload, collection=self.collection_name, score=point.score)
            for point in results.points
        ]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_rag_retrieval.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add tools/rag/retrieval.py tests/test_rag_retrieval.py
git commit -m "$(cat <<'EOF'
Add hybrid dense+sparse RRF retrieval for a single Qdrant collection

HybridRetriever takes an already-constructed client/dense_model/
sparse_model — model lifecycle is the pipeline layer's job, not this
one's, so this stays testable with fakes instead of real bge-m3/BM25.
EOF
)"
```

---

### Task 5: Cross-encoder reranking

**Files:**
- Create: `tools/rag/reranking.py`
- Create: `tests/test_rag_reranking.py`

**Interfaces:**
- Consumes: `tools.rag.models.ScoredChunk` (Task 1)
- Produces: `tools.rag.reranking.BaseReranker`, `tools.rag.reranking.CrossEncoderReranker` — `CrossEncoderReranker(model, batch_size=16).rerank(query, chunks) -> list[ScoredChunk]`, sorted descending by the new score.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_rag_reranking.py`:

```python
"""Tests for tools/rag/reranking.py. Uses a fake CrossEncoder — no real
bge-reranker-v2-m3 model load in this suite."""

from tools.rag.models import ScoredChunk
from tools.rag.reranking import CrossEncoderReranker


class _FakeCrossEncoder:
    def __init__(self, scores):
        self._scores = scores
        self.last_pairs = None
        self.last_batch_size = None

    def predict(self, pairs, batch_size=16):
        self.last_pairs = pairs
        self.last_batch_size = batch_size
        return self._scores


def _chunk(id_, text, score=0.0):
    return ScoredChunk(
        id=id_, text=text, book="b", chapter="1",
        collection="principles", chunk_index=0, metadata=None, score=score,
    )


def test_rerank_sorts_by_new_scores_descending():
    chunks = [_chunk("a", "text a"), _chunk("b", "text b"), _chunk("c", "text c")]
    fake_model = _FakeCrossEncoder(scores=[0.1, 0.9, 0.5])
    reranker = CrossEncoderReranker(model=fake_model)

    result = reranker.rerank(query="q", chunks=chunks)

    assert [c.id for c in result] == ["b", "c", "a"]
    assert [c.score for c in result] == [0.9, 0.5, 0.1]
    assert fake_model.last_pairs == [("q", "text a"), ("q", "text b"), ("q", "text c")]


def test_rerank_empty_list_returns_empty_without_calling_model():
    fake_model = _FakeCrossEncoder(scores=[])
    reranker = CrossEncoderReranker(model=fake_model)

    assert reranker.rerank(query="q", chunks=[]) == []
    assert fake_model.last_pairs is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_rag_reranking.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.rag.reranking'`

- [ ] **Step 3: Create `tools/rag/reranking.py`**

```python
"""
Cross-encoder reranking over already-retrieved chunks. `model` is an
already-constructed CrossEncoder (model lifecycle belongs to
tools/rag/pipeline.py) — keeps this trivially testable with a fake.
"""

from abc import ABC, abstractmethod

from sentence_transformers import CrossEncoder

from tools.rag.models import ScoredChunk


class BaseReranker(ABC):
    @abstractmethod
    def rerank(self, query: str, chunks: list[ScoredChunk]) -> list[ScoredChunk]:
        pass


class CrossEncoderReranker(BaseReranker):
    def __init__(self, model: CrossEncoder, batch_size: int = 16):
        self.model = model
        self.batch_size = batch_size

    def rerank(self, query: str, chunks: list[ScoredChunk]) -> list[ScoredChunk]:
        if not chunks:
            return []

        pairs = [(query, chunk.text) for chunk in chunks]
        scores = self.model.predict(pairs, batch_size=self.batch_size)

        reranked = [
            chunk.model_copy(update={"score": float(score)})
            for chunk, score in zip(chunks, scores)
        ]

        return sorted(reranked, key=lambda chunk: chunk.score, reverse=True)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_rag_reranking.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add tools/rag/reranking.py tests/test_rag_reranking.py
git commit -m "$(cat <<'EOF'
Add cross-encoder reranking over retrieved chunks

CrossEncoderReranker takes an already-constructed model, same pattern as
HybridRetriever — pipeline.py owns model lifecycle, this owns the sort.
EOF
)"
```

---

### Task 6: Pipeline orchestration + real model/Qdrant wiring

**Files:**
- Create: `tools/rag/pipeline.py`
- Modify: `tools/rag/__init__.py` (replace the old inline stub with a re-export)
- Modify: `config.py` (add `RAG_DATA_DIR`, `QDRANT_PATH`, `RAG_MODELS_DIR`)
- Create: `tests/test_rag_pipeline.py`

**Interfaces:**
- Consumes: everything from Tasks 1-5 (`tools.rag.models`, `tools.rag.filtering`, `tools.rag.retrieval`, `tools.rag.reranking`); `agents.llm.get_llm`
- Produces: `tools.rag.pipeline.search_rag` (the `@tool`), `tools.rag.pipeline.route_collections`, `tools.rag.pipeline.format_results` — re-exported as `tools.rag.search_rag`, the contract `agents/exercise_recommender.py` depends on.

This is the task that actually deletes the old static stub's behavior. Everything up to the real-model loading (`_ensure_loaded`) is tested with fakes, matching every prior task; `_ensure_loaded` itself (real HuggingFace downloads + real Qdrant + real Azure OpenAI) is verified manually at the end, per this project's existing convention of not exercising live external services in `tests/`.

- [ ] **Step 1: Add the new path constants to `config.py`**

In `config.py`, after the existing `PROMPTS_DIR = BASE_DIR / "prompts"` line, add:

```python
RAG_DATA_DIR = BASE_DIR / "rag_data"
QDRANT_PATH = RAG_DATA_DIR / "qdrant"
RAG_MODELS_DIR = DATA_DIR / "models"
```

(`DATA_DIR` already exists two lines above — this reuses it rather than introducing a new top-level folder, so `RAG_MODELS_DIR` is covered by the existing `data/` line in `.gitignore` with no `.gitignore` change needed.)

- [ ] **Step 2: Write the failing tests for `route_collections` and `format_results`**

Create `tests/test_rag_pipeline.py`:

```python
"""Tests for tools/rag/pipeline.py. route_collections and format_results
are pure. search_rag's orchestration is tested by monkeypatching
_ensure_loaded (a no-op) and _retrieve_collection (returns fixed
ScoredChunks) plus a fake reranker in _state — no real model load, no
real Qdrant, no real LLM call, matching this project's test conventions.
Real model/Qdrant/LLM wiring inside _ensure_loaded is verified manually
(see the plan's Step 8), not by this suite."""

import tools.rag.pipeline as pipeline
from tools.rag.models import ScoredChunk


def _chunk(id_, text, score, collection="principles"):
    return ScoredChunk(
        id=id_, text=text, book="testbook", chapter="1",
        collection=collection, chunk_index=0, metadata=None, score=score,
    )


def test_route_collections_hypertrophy_goal():
    assert pipeline.route_collections("hypertrophy") == ["hypertrophy", "principles"]


def test_route_collections_strength_goal():
    assert pipeline.route_collections("strength") == ["strength", "principles"]


def test_route_collections_unknown_goal_falls_back_to_principles_only():
    assert pipeline.route_collections("fat_loss") == ["principles"]
    assert pipeline.route_collections("") == ["principles"]
    assert pipeline.route_collections("not_a_real_goal") == ["principles"]


def test_format_results_empty_list():
    assert "No relevant results found" in pipeline.format_results([])


def test_format_results_includes_source_attribution_in_order():
    chunks = [
        _chunk("a", "first chunk text", 0.9, "hypertrophy"),
        _chunk("b", "second chunk text", 0.4, "principles"),
    ]
    result = pipeline.format_results(chunks)

    assert result.index("first chunk text") < result.index("second chunk text")
    assert "book: testbook" in result
    assert "chapter: 1" in result
    assert "collection: hypertrophy" in result
    assert "collection: principles" in result
    assert "score=0.90" in result


class _FakeReranker:
    def rerank(self, query, chunks):
        return sorted(chunks, key=lambda c: c.score, reverse=True)


def test_search_rag_routes_merges_reranks_and_truncates_to_top3(monkeypatch):
    monkeypatch.setattr(pipeline, "_ensure_loaded", lambda: None)
    # A fresh dict via monkeypatch (not pipeline._state["reranker"] = ...) so
    # the replacement is reverted after this test instead of leaking into
    # whichever test runs next — _state is process-global module state.
    monkeypatch.setattr(pipeline, "_state", {"reranker": _FakeReranker()})

    calls = []

    def fake_retrieve(collection, query):
        calls.append(collection)
        if collection == "hypertrophy":
            return [
                _chunk("h1", "hyp text high", 0.9, "hypertrophy"),
                _chunk("h2", "hyp text low", 0.2, "hypertrophy"),
            ]
        return [
            _chunk("p1", "principles text high", 0.95, "principles"),
            _chunk("p2", "principles text lowest", 0.05, "principles"),
        ]

    monkeypatch.setattr(pipeline, "_retrieve_collection", fake_retrieve)

    result = pipeline.search_rag.invoke(
        {"muscle_group": "chest", "query": "compound movements", "goal": "hypertrophy"}
    )

    assert calls == ["hypertrophy", "principles"]
    assert "principles text high" in result
    assert "hyp text high" in result
    assert "hyp text low" in result
    assert "principles text lowest" not in result  # 4th place, dropped by top-3


def test_search_rag_unrecognized_goal_only_queries_principles(monkeypatch):
    monkeypatch.setattr(pipeline, "_ensure_loaded", lambda: None)
    monkeypatch.setattr(pipeline, "_state", {"reranker": _FakeReranker()})

    calls = []

    def fake_retrieve(collection, query):
        calls.append(collection)
        return [_chunk("p1", "principles text", 0.5, "principles")]

    monkeypatch.setattr(pipeline, "_retrieve_collection", fake_retrieve)

    pipeline.search_rag.invoke(
        {"muscle_group": "chest", "query": "general fitness advice", "goal": "general_fitness"}
    )

    assert calls == ["principles"]
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `pytest tests/test_rag_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.rag.pipeline'`

- [ ] **Step 4: Create `tools/rag/pipeline.py`**

```python
"""
Orchestrates the RAG pipeline behind the search_rag tool: lazily loads and
caches the embedding/reranker models and Qdrant client as module-level
state (first call pays the cost, every call after is fast — guarded by a
lock since deepagents can dispatch concurrent exercise-recommender calls
within the same process, same reasoning as tools/memory.py's
_progress_lock), routes each query to the collection(s) matching the
plan's paradigm, runs metadata-filtered hybrid search per collection,
reranks the merged candidates, and formats the top 3 for the calling
agent.
"""

import threading

from fastembed import SparseTextEmbedding
from langchain_core.tools import tool
from qdrant_client import QdrantClient
from qdrant_client.models import Filter
from sentence_transformers import CrossEncoder, SentenceTransformer

from agents.llm import get_llm
from config import QDRANT_PATH, RAG_MODELS_DIR
from tools.rag.filtering import (
    GoalFilterBuilder,
    GoalMetadataExtractor,
    PrinciplesFilterBuilder,
    PrinciplesMetadataExtractor,
)
from tools.rag.models import ScoredChunk
from tools.rag.reranking import CrossEncoderReranker
from tools.rag.retrieval import HybridRetriever

COLLECTION_BY_GOAL = {
    "hypertrophy": "hypertrophy",
    "strength": "strength",
}

_lock = threading.Lock()
_state: dict = {}


def _ensure_loaded() -> None:
    if _state:
        return
    with _lock:
        if _state:
            return

        RAG_MODELS_DIR.mkdir(parents=True, exist_ok=True)

        dense_model_path = RAG_MODELS_DIR / "bge-m3"
        if dense_model_path.exists():
            dense_model = SentenceTransformer(str(dense_model_path), device="cpu")
        else:
            dense_model = SentenceTransformer("BAAI/bge-m3", device="cpu")
            dense_model.save(str(dense_model_path))

        reranker_model_path = RAG_MODELS_DIR / "bge-reranker-v2-m3"
        if reranker_model_path.exists():
            reranker_model = CrossEncoder(str(reranker_model_path), device="cpu")
        else:
            reranker_model = CrossEncoder("BAAI/bge-reranker-v2-m3", device="cpu")
            reranker_model.save(str(reranker_model_path))

        fastembed_dir = RAG_MODELS_DIR / "fastembed"
        fastembed_dir.mkdir(parents=True, exist_ok=True)
        sparse_model = SparseTextEmbedding(
            model_name="Qdrant/bm25",
            cache_dir=str(fastembed_dir),
        )

        client = QdrantClient(path=str(QDRANT_PATH))

        llm = get_llm(temperature=0)

        _state["client"] = client
        _state["dense_model"] = dense_model
        _state["sparse_model"] = sparse_model
        _state["reranker"] = CrossEncoderReranker(model=reranker_model)
        _state["goal_extractor"] = GoalMetadataExtractor(llm=llm)
        _state["principles_extractor"] = PrinciplesMetadataExtractor(llm=llm)
        _state["goal_filter_builder"] = GoalFilterBuilder()
        _state["principles_filter_builder"] = PrinciplesFilterBuilder()


def route_collections(goal: str) -> list[str]:
    goal_collection = COLLECTION_BY_GOAL.get(goal)
    if goal_collection:
        return [goal_collection, "principles"]
    return ["principles"]


def _filter_for_collection(collection: str, query: str) -> Filter:
    if collection == "principles":
        query_filter = _state["principles_extractor"].extract(query)
        return _state["principles_filter_builder"].build(query_filter)

    query_filter = _state["goal_extractor"].extract(query)
    return _state["goal_filter_builder"].build(query_filter)


def _retrieve_collection(collection: str, query: str) -> list[ScoredChunk]:
    qdrant_filter = _filter_for_collection(collection, query)
    retriever = HybridRetriever(
        client=_state["client"],
        collection_name=collection,
        dense_model=_state["dense_model"],
        sparse_model=_state["sparse_model"],
        top_k=10,
    )
    return retriever.retrieve(query=query, query_filter=qdrant_filter)


def format_results(chunks: list[ScoredChunk]) -> str:
    if not chunks:
        return "=== RAG RESULTS (top 3, reranked) ===\nNo relevant results found."

    blocks = [
        f"[{i}] score={chunk.score:.2f} | book: {chunk.book} | "
        f"chapter: {chunk.chapter} | collection: {chunk.collection}\n{chunk.text}"
        for i, chunk in enumerate(chunks, start=1)
    ]

    return "=== RAG RESULTS (top 3, reranked) ===\n\n" + "\n\n".join(blocks)


@tool
def search_rag(muscle_group: str, query: str, goal: str) -> str:
    """
    Search the RAG knowledge base for training principles and muscle-specific
    guidance, filtered by the plan's paradigm.

    Args:
        muscle_group: The underlying muscle key (e.g. "chest", "legs",
            "back") — not a specific muscle_group ID like "legs_a".
        query: What you need, e.g. "hypertrophy chest compound movements".
        goal: The plan's paradigm (e.g. "hypertrophy", "strength",
            "fat_loss") — read from the Paradigm: line in the User Profile.
            Routes the search to the matching knowledge-base collection.

    Returns the top 3 most relevant chunks after hybrid retrieval and
    cross-encoder reranking, with source attribution.
    """
    _ensure_loaded()

    combined_query = f"{muscle_group}: {query}"
    collections = route_collections(goal)

    candidates: list[ScoredChunk] = []
    for collection in collections:
        candidates.extend(_retrieve_collection(collection, combined_query))

    reranked = _state["reranker"].rerank(query=combined_query, chunks=candidates)
    top3 = reranked[:3]

    return format_results(top3)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_rag_pipeline.py -v`
Expected: PASS (7 tests)

- [ ] **Step 6: Replace `tools/rag/__init__.py`'s content**

Replace the entire file with:

```python
"""
RAG knowledge base — real hybrid search + reranking pipeline. See
tools/rag/pipeline.py for the implementation; this module only re-exports
the tool contract other code depends on.
"""

from tools.rag.pipeline import search_rag

__all__ = ["search_rag"]
```

- [ ] **Step 7: Run the full test suite**

Run: `pytest tests/ -q`
Expected: PASS — every test from Tasks 1-6, plus all pre-existing tests (`test_dev_login.py`, `test_workout_feedback.py`, `test_session_ownership.py`, `test_session_plan.py`, etc.) still pass, confirming `agents/exercise_recommender.py`'s `from tools.rag import search_rag` still resolves correctly now that it points at the real pipeline.

- [ ] **Step 8: Manual smoke test (real models + real Qdrant + real Azure OpenAI — not run in `pytest`)**

This exercises `_ensure_loaded`'s real branch, which downloads ~2-3GB from HuggingFace on first run and requires the `.env` Azure OpenAI credentials to already be configured (per `config.py`) — the same reason `agents/plan_adjuster.py` is excluded from the automated suite. Run interactively from the repo root:

```bash
python -c "
from tools.rag import search_rag
result = search_rag.invoke({
    'muscle_group': 'chest',
    'query': 'compound movements for hypertrophy',
    'goal': 'hypertrophy',
})
print(result)
"
```

Expected: first run prints `Downloading BAAI/bge-m3...` (or similar) and takes a while; subsequent runs are fast. Output starts with `=== RAG RESULTS (top 3, reranked) ===` followed by exactly 3 numbered blocks, each with a `book:`/`chapter:`/`collection:` line and chunk text, with `collection:` values drawn from `hypertrophy` and/or `principles` (never `strength`, since `goal="hypertrophy"`). Note how long this takes end-to-end (excluding the one-time download) — this is the number to check against the "latency is ok, I'll test it" call from the design discussion.

- [ ] **Step 9: Commit**

```bash
git add tools/rag/pipeline.py tools/rag/__init__.py config.py tests/test_rag_pipeline.py
git commit -m "$(cat <<'EOF'
Wire the real RAG pipeline behind search_rag

Replaces the static stub entirely: routes by paradigm to the matching
Qdrant collection(s), narrows with LLM-extracted metadata filters,
retrieves top 10 per collection via hybrid RRF search, reranks the merged
candidates, and returns the top 3 with source attribution. Models and
Qdrant are lazily loaded module-level singletons, guarded by a lock for
concurrent exercise-recommender dispatches.
EOF
)"
```

---

### Task 7: Update the exercise-recommender prompt to pass `goal`

**Files:**
- Modify: `prompts/exercise_recommender.md`
- Create: `tests/test_exercise_recommender_prompt.py`

**Interfaces:**
- Consumes: `config.load_prompt` (existing)
- Produces: nothing new — this is the last piece wiring the paradigm value (already read by the agent in step 1) into the new `goal` argument added in Task 6.

- [ ] **Step 1: Write the failing test**

Create `tests/test_exercise_recommender_prompt.py`:

```python
"""Confirms the exercise_recommender prompt tells the agent to pass the
plan's paradigm as search_rag's goal argument — a plain-text assertion
since the prompt itself is only ever consumed by an LLM, not by code."""

from config import load_prompt


def test_prompt_instructs_passing_goal_to_search_rag():
    text = load_prompt("exercise_recommender")
    assert "goal set to the plan's Paradigm value" in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_exercise_recommender_prompt.py -v`
Expected: FAIL — assertion error, the phrase isn't in the prompt yet.

- [ ] **Step 3: Edit `prompts/exercise_recommender.md`**

Replace:

```
2. Call search_rag with the underlying muscle key and a query describing what you need
   (e.g. "hypertrophy chest compound movements"). If you were given an emphasis brief
   (legs_a/legs_b), reflect it in the query (e.g. "quad-dominant squat pattern exercises").
```

with:

```
2. Call search_rag with the underlying muscle key, a query describing what you need
   (e.g. "hypertrophy chest compound movements"), and goal set to the plan's Paradigm value
   from step 1 (e.g. "hypertrophy", "strength") - this routes your search to the matching
   knowledge-base collection. If you were given an emphasis brief (legs_a/legs_b), reflect it
   in the query (e.g. "quad-dominant squat pattern exercises").
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_exercise_recommender_prompt.py -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite one last time**

Run: `pytest tests/ -q`
Expected: PASS (all tests, project-wide)

- [ ] **Step 6: Commit**

```bash
git add prompts/exercise_recommender.md tests/test_exercise_recommender_prompt.py
git commit -m "$(cat <<'EOF'
Pass the plan's paradigm to search_rag as the new goal argument

Completes the RAG retrieval integration: the agent already reads the
Paradigm field for the intensity tables (step 1) and now reuses that same
value to route search_rag to the matching Qdrant collection.
EOF
)"
```
