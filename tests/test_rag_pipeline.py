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
