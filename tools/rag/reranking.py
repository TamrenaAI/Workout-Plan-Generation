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
