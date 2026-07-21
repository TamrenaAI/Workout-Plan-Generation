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
    global _state
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

        # Build the fully-populated state locally, then rebind the module
        # name in one atomic statement — populating the module-level dict
        # key-by-key would let a concurrent, unlocked `if _state:` fast-path
        # check observe a partially-built state (truthy after the first key
        # write, but missing the rest) and proceed to use it.
        _state = {
            "client": client,
            "dense_model": dense_model,
            "sparse_model": sparse_model,
            "reranker": CrossEncoderReranker(model=reranker_model),
            "goal_extractor": GoalMetadataExtractor(llm=llm),
            "principles_extractor": PrinciplesMetadataExtractor(llm=llm),
            "goal_filter_builder": GoalFilterBuilder(),
            "principles_filter_builder": PrinciplesFilterBuilder(),
        }


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
def search_rag(muscle_group: str, query: str, goal: str = "") -> str:
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
