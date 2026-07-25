from abc import ABC, abstractmethod
from .models import ScoredChunk
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Filter,
)
from sentence_transformers import SentenceTransformer, CrossEncoder
from fastembed import SparseTextEmbedding
from .qdrant import hybrid_search
from .metadata import BaseMetadataExtractor
from .filters import BaseFilterBuilder
from .rerankers import BaseReranker

class BaseRetriever(ABC):

    @abstractmethod
    def retrieve(
        self,
        query: str,
        query_filter=None,
    ) -> list[ScoredChunk]:
        """
        Retrieve the most relevant chunk indices
        for a given query.
        """
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

    def retrieve(
        self,
        query: str,
        query_filter: Filter | None = None,
    ) -> list[ScoredChunk]:

        results = hybrid_search(
            client=self.client,
            collection_name=self.collection_name,
            query=query,
            dense_model=self.dense_model,
            sparse_model=self.sparse_model,
            top_k=self.top_k,
            query_filter=query_filter,
        )


        retrieved_chunks = []

        for point in results.points:

            retrieved_chunks.append(
                ScoredChunk(
                    **point.payload,
                    collection=self.collection_name,
                    score=point.score,
                )
            )

        return retrieved_chunks
    

class FilteredHybridRetriever(BaseRetriever):

    def __init__(
        self,
        retriever: HybridRetriever,
        metadata_extractor: BaseMetadataExtractor,
        filter_builder: BaseFilterBuilder,
    ):
        self.retriever = retriever
        self.metadata_extractor = metadata_extractor
        self.filter_builder = filter_builder

    def retrieve(
        self,
        query: str,
    ) -> list[ScoredChunk]:

        query_filter = self.metadata_extractor.extract(query)

        qdrant_filter = self.filter_builder.build(query_filter)

        return self.retriever.retrieve(
            query=query,
            query_filter=qdrant_filter,
        )


class RerankingRetriever(BaseRetriever):

    def __init__(
        self,
        retriever: BaseRetriever,
        reranker: BaseReranker,
        top_k: int = 3,
    ):
        self.retriever = retriever
        self.reranker = reranker
        self.top_k = top_k

    def retrieve(
        self,
        query: str,
    ) -> list[ScoredChunk]:

        chunks = self.retriever.retrieve(query=query)

        reranked_chunks = self.reranker.rerank(
            query=query,
            chunks=chunks,
        )

        return reranked_chunks[: self.top_k]


