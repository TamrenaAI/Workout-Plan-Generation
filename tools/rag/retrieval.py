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
