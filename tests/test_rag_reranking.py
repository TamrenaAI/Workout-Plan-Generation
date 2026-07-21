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
