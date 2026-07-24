from pathlib import Path

from sentence_transformers import SentenceTransformer, CrossEncoder
from fastembed import SparseTextEmbedding
from .models import Chunk
import numpy as np
from rag_pipeline.paths import FASTEMBED_DIR, DENSE_DIR, RERANKER_DIR


def load_dense_model()-> SentenceTransformer:
    return SentenceTransformer(
        str(DENSE_DIR)
    )


def load_reranker() -> CrossEncoder:
    return CrossEncoder(
        str(RERANKER_DIR)
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







