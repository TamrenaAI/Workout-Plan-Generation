from qdrant_client import QdrantClient
from .models import CollectionName
from sentence_transformers import SentenceTransformer, CrossEncoder
from fastembed import SparseTextEmbedding
from .retrievers import(
    HybridRetriever, FilteredHybridRetriever,BaseRetriever,
    RerankingRetriever,
)
from langchain_core.language_models.chat_models import BaseChatModel
from .metadata import PrinciplesMetadataExtractor, GoalMetadataExtractor
from .filters import PrinciplesFilterBuilder, GoalFilterBuilder
from .rerankers import BaseReranker
from langchain_core.prompts import ChatPromptTemplate

from .rag import BaseRAG, RAG


def create_hybrid_retriever(
    client: QdrantClient,
    collection_name: CollectionName,
    dense_model: SentenceTransformer,
    sparse_model: SparseTextEmbedding,
    top_k: int = 10,
) -> HybridRetriever:
    """
    Create a HybridRetriever configured for a specific collection.
    """

    return HybridRetriever(
        client=client,
        collection_name=collection_name,
        dense_model=dense_model,
        sparse_model=sparse_model,
        top_k=top_k,
    )


def create_filtered_retriever(
    retriever: HybridRetriever,
    collection_name: CollectionName,
    llm: BaseChatModel,
) -> FilteredHybridRetriever:
    
    if collection_name == "principles":
        metadata_extractor = PrinciplesMetadataExtractor(
            llm=llm,
        )

        filter_builder = PrinciplesFilterBuilder()

    else:
        metadata_extractor = GoalMetadataExtractor(
            llm=llm,
        )

        filter_builder = GoalFilterBuilder()

    return FilteredHybridRetriever(
        retriever=retriever,
        metadata_extractor=metadata_extractor,
        filter_builder=filter_builder,
    )


def create_reranking_retriever(
    retriever: BaseRetriever,
    reranker: BaseReranker,
    top_k: int = 3,
) -> RerankingRetriever:
    """
    Create a retriever that reranks retrieved chunks.
    """

    return RerankingRetriever(
        retriever=retriever,
        reranker=reranker,
        top_k=top_k,
    )


def create_rag(
    retriever: BaseRetriever,
    llm: BaseChatModel,
    prompt: ChatPromptTemplate,
) -> RAG:
    """
    Create a RAG pipeline.
    """

    return RAG(
        retriever=retriever,
        llm=llm,
        prompt=prompt,
    )

