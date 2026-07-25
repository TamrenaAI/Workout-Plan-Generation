from pathlib import Path

from sentence_transformers import SentenceTransformer, CrossEncoder
from fastembed import SparseTextEmbedding
from .models import Chunk
import numpy as np
from rag_pipeline.paths import FASTEMBED_DIR, DENSE_DIR, RERANKER_DIR
from qdrant_client.models import (
    SparseVector,
)

def load_dense_model()-> SentenceTransformer:
    return SentenceTransformer(
        str(DENSE_DIR),
        device="cpu"
    )


def load_sparse_model() -> SparseTextEmbedding:

    FASTEMBED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    return SparseTextEmbedding(
        model_name="Qdrant/bm25",
        cache_dir=str(FASTEMBED_DIR),
    )


def get_chunk_texts(
    chunks: list[Chunk],
) -> list[str]:

    return [
        chunk.text
        for chunk in chunks
    ]


def embed_dense_batch(
    chunks: list[Chunk],
    model: SentenceTransformer,
) -> np.ndarray:

    return model.encode(
        get_chunk_texts(chunks),
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )

def embed_sparse_batch(
    chunks: list[Chunk],
    model: SparseTextEmbedding,
):
    return list(
        model.embed(
            get_chunk_texts(chunks),
        )
    )


def embed_dense_query(
    query: str,
    model: SentenceTransformer,
) -> list[float]:

    return model.encode(
        query,
        normalize_embeddings=True,
        convert_to_numpy=True,
    ).tolist()


def embed_sparse_query(
    query: str,
    model: SparseTextEmbedding,
) -> SparseVector:

    sparse = list(
        model.embed([query])
    )[0]

    return SparseVector(
        indices=sparse.indices.tolist(),
        values=sparse.values.tolist(),
    )
