from collections import defaultdict
from tqdm import tqdm
from rag_pipeline.models import Chunk, COLLECTIONS

from sentence_transformers import SentenceTransformer
from fastembed import SparseTextEmbedding
from qdrant_client import QdrantClient
from rag_pipeline.utils import batch_iterator
from rag_pipeline.embeddings import(
    embed_dense_batch, embed_sparse_batch,
    load_dense_model, load_sparse_model
)
from rag_pipeline.qdrant import(
    create_collections,
    create_qdrant_client,
    build_points,
    upsert_batch
)


from rag_pipeline.storage import load_all_chunks

import argparse

from rag_pipeline.paths import get_book_paths
from pathlib import Path


def ingest_chunks(
    chunks: list[Chunk],
    client: QdrantClient,
    dense_model: SentenceTransformer,
    sparse_model: SparseTextEmbedding,
    batch_size: int = 64,
) -> None:

    total_batches = (len(chunks) + batch_size - 1) // batch_size

    for batch in tqdm(
        batch_iterator(chunks, batch_size),
        total=total_batches,
        desc="Ingesting Chunks",
    ):
        
        dense_vectors = embed_dense_batch(
            chunks=batch,
            model=dense_model,
        )

        sparse_vectors = embed_sparse_batch(
            chunks=batch,
            model=sparse_model,
        )

        grouped = defaultdict(list)

        for chunk, dense, sparse in zip(
            batch,
            dense_vectors,
            sparse_vectors,
        ):
            grouped[chunk.collection].append(
                (
                    chunk,
                    dense,
                    sparse,
                )
            )

        for collection_name, items in grouped.items():

            group_chunks = [item[0] for item in items]
            group_dense = [item[1] for item in items]
            group_sparse = [item[2] for item in items]

            points = build_points(
                chunks=group_chunks,
                dense_vectors=group_dense,
                sparse_vectors=group_sparse,
            )

            upsert_batch(
                client=client,
                collection_name=collection_name,
                points=points,
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate embeddings and index chunks into Qdrant."
    )

    parser.add_argument(
        "book",
        help="Book directory name.",
    )

    return parser.parse_args()



def main():

    args = parse_args()

    paths = get_book_paths(args.book)


    chunks = load_all_chunks(
        paths.chunks_dir,
    )

    dense_model = load_dense_model()
    dense_size = dense_model.get_embedding_dimension()

    sparse_model = load_sparse_model()

    client = create_qdrant_client()

    create_collections(
        client=client,
        collections=COLLECTIONS,
        desnse_size=dense_size,
        recreate=False)

    ingest_chunks(
        chunks=chunks,
        client=client,
        dense_model=dense_model,
        sparse_model=sparse_model,
        batch_size=64,
    )

if __name__ == "__main__":
    main()


