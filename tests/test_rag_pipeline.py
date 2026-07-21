"""Tests for tools/rag/pipeline.py. route_collections and format_results
are pure. search_rag's orchestration is tested by monkeypatching
_ensure_loaded (a no-op) and _retrieve_collection (returns fixed
ScoredChunks) plus a fake reranker in _state — no real model load, no
real Qdrant, no real LLM call, matching this project's test conventions.
Real model/Qdrant/LLM wiring inside _ensure_loaded is verified manually
(see the plan's Step 8), not by this suite."""

from qdrant_client.models import Filter

import tools.rag.pipeline as pipeline
from tools.rag.models import GoalQueryFilter, PrinciplesQueryFilter, ScoredChunk


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


class _FakeExtractor:
    def __init__(self, value):
        self.value = value
        self.queries_seen = []

    def extract(self, query):
        self.queries_seen.append(query)
        return self.value


class _FakeFilterBuilder:
    def __init__(self, filter_to_return):
        self.filter_to_return = filter_to_return
        self.built_from = []

    def build(self, query_filter):
        self.built_from.append(query_filter)
        return self.filter_to_return


class _FakeDenseModel:
    def encode(self, query, normalize_embeddings=True, convert_to_numpy=True):
        import numpy as np
        return np.array([0.1, 0.2, 0.3])


class _FakeSparseEmbedding:
    def __init__(self):
        import numpy as np
        self.indices = np.array([1])
        self.values = np.array([0.5])


class _FakeSparseModel:
    def embed(self, texts):
        return [_FakeSparseEmbedding() for _ in texts]


class _FakeQdrantClientForFilter:
    def __init__(self):
        self.last_call_kwargs = None

    def query_points(self, **kwargs):
        self.last_call_kwargs = kwargs

        class _EmptyResponse:
            points = []

        return _EmptyResponse()


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


def test_filter_for_collection_uses_principles_extractor_and_builder(monkeypatch):
    principles_filter_value = PrinciplesQueryFilter(topic=["volume"])
    goal_filter_value = GoalQueryFilter(muscle=["chest"])
    principles_extractor = _FakeExtractor(principles_filter_value)
    goal_extractor = _FakeExtractor(goal_filter_value)
    built_principles_filter = Filter(must=[])
    principles_builder = _FakeFilterBuilder(built_principles_filter)
    goal_builder = _FakeFilterBuilder(Filter(must=[]))

    monkeypatch.setattr(pipeline, "_state", {
        "principles_extractor": principles_extractor,
        "goal_extractor": goal_extractor,
        "principles_filter_builder": principles_builder,
        "goal_filter_builder": goal_builder,
    })

    result = pipeline._filter_for_collection("principles", "some query")

    assert principles_extractor.queries_seen == ["some query"]
    assert goal_extractor.queries_seen == []
    assert principles_builder.built_from == [principles_filter_value]
    assert goal_builder.built_from == []
    assert result is built_principles_filter


def test_filter_for_collection_uses_goal_extractor_and_builder_for_goal_collections(monkeypatch):
    principles_filter_value = PrinciplesQueryFilter(topic=["volume"])
    goal_filter_value = GoalQueryFilter(muscle=["chest"])
    principles_extractor = _FakeExtractor(principles_filter_value)
    goal_extractor = _FakeExtractor(goal_filter_value)
    built_goal_filter = Filter(must=[])
    principles_builder = _FakeFilterBuilder(Filter(must=[]))
    goal_builder = _FakeFilterBuilder(built_goal_filter)

    monkeypatch.setattr(pipeline, "_state", {
        "principles_extractor": principles_extractor,
        "goal_extractor": goal_extractor,
        "principles_filter_builder": principles_builder,
        "goal_filter_builder": goal_builder,
    })

    result = pipeline._filter_for_collection("hypertrophy", "chest compound movements")

    assert goal_extractor.queries_seen == ["chest compound movements"]
    assert principles_extractor.queries_seen == []
    assert goal_builder.built_from == [goal_filter_value]
    assert principles_builder.built_from == []
    assert result is built_goal_filter


def test_retrieve_collection_threads_built_filter_into_hybrid_retriever(monkeypatch):
    fake_filter = Filter(must=[])
    fake_client = _FakeQdrantClientForFilter()

    monkeypatch.setattr(pipeline, "_state", {
        "client": fake_client,
        "dense_model": _FakeDenseModel(),
        "sparse_model": _FakeSparseModel(),
        "principles_extractor": _FakeExtractor(PrinciplesQueryFilter()),
        "principles_filter_builder": _FakeFilterBuilder(fake_filter),
    })

    pipeline._retrieve_collection("principles", "chest exercises")

    assert fake_client.last_call_kwargs["collection_name"] == "principles"
    assert fake_client.last_call_kwargs["query_filter"] is fake_filter
    assert fake_client.last_call_kwargs["limit"] == 10
