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
