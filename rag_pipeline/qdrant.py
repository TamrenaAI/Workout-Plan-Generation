from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    SparseVectorParams,
    Distance,
    PointStruct,
    SparseVector,
    Prefetch,
    FusionQuery,
    Fusion,
    Filter,
)

import uuid

from .models import Chunk
from .paths import QDRANT_DIR
from sentence_transformers import SentenceTransformer, CrossEncoder
from fastembed import SparseTextEmbedding
from .embeddings import embed_sparse_query, embed_dense_query


def create_qdrant_client() -> QdrantClient:

    qdrant = QdrantClient(
        path=QDRANT_DIR,
    )

    return qdrant


def create_collections(
    client: QdrantClient,
    collections: list[str],
    desnse_size: int,
    recreate: bool = False
) -> None:

    

    for collection in collections:
        if recreate and client.collection_exists(collection):
            client.delete_collection(collection_name=collection)
            print(f"Deleted old {collection}")

        if not client.collection_exists(collection):
            client.create_collection(
                collection_name=collection,
                vectors_config={
                    "dense": VectorParams(
                        size=desnse_size,
                        distance=Distance.COSINE,
                    ),
                },
                sparse_vectors_config={
                    "sparse": SparseVectorParams(),
                },
            )
            print(f"Created {collection}")
        else:
            print(f"{collection} already exists.")


def build_points(
    chunks: list[Chunk],
    dense_vectors,
    sparse_vectors,
) -> list[PointStruct]:

    points = []

    for chunk, dense, sparse in zip(
        chunks,
        dense_vectors,
        sparse_vectors,
    ):
        point_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_DNS,
                chunk.id,
            )
        )
        point = PointStruct(
            id=point_id,
            vector={
                "dense": dense.tolist(),
                "sparse": SparseVector(
                    indices=sparse.indices.tolist(),
                    values=sparse.values.tolist(),
                ),
            },
            payload = chunk.model_dump(
                exclude={
                    "collection",
                },
            ),
        )

        points.append(point)

    return points


def upsert_batch(
    client: QdrantClient,
    collection_name: str,
    points: list[PointStruct],
) -> None:

    client.upsert(
        collection_name=collection_name,
        points=points,
        wait=True,
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

    dense_vector = embed_dense_query(
        query=query,
        model=dense_model,
    )

    sparse_vector = embed_sparse_query(
        query=query,
        model=sparse_model,
    )

    return client.query_points(
        collection_name=collection_name,

        prefetch=[
            Prefetch(
                using="dense",
                query=dense_vector,
                limit=top_k,
            ),
            Prefetch(
                using="sparse",
                query=sparse_vector,
                limit=top_k,
            ),
        ],

        query=FusionQuery(
            fusion=Fusion.RRF,
        ),

        query_filter=query_filter,

        limit=top_k,
        with_payload=True,
    )

