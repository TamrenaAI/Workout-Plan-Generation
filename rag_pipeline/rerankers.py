from abc import ABC, abstractmethod
from .models import ScoredChunk
from sentence_transformers import CrossEncoder



class BaseReranker(ABC):

    @abstractmethod
    def rerank(
        self,
        query: str,
        chunks: list[ScoredChunk],
    ) -> list[ScoredChunk]:
        """
        Re-rank retrieved chunks according to their relevance to the query.
        """
        ...


class CrossEncoderReranker(BaseReranker):

    def __init__(
        self,
        model_name: str,
        device: str | None = None,
        batch_size: int = 16,
    ):
        self.batch_size = batch_size
        self.model = CrossEncoder(
            model_name,
            device=device,
        )

    def rerank(
        self,
        query: str,
        chunks: list[ScoredChunk],
    ) -> list[ScoredChunk]:

        pairs = [
            (query, chunk.text)
            for chunk in chunks
        ]

        scores = self.model.predict(
            pairs,
            batch_size=self.batch_size,
        )

        reranked_chunks = [
            chunk.model_copy(
                update={"score": float(score)}
            )
            for chunk, score in zip(chunks, scores)
        ]

        return sorted(
            reranked_chunks,
            key=lambda chunk: chunk.score,
            reverse=True,
        )