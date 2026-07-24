from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams,
    SparseVectorParams,
    Distance,
    PointStruct,
    SparseVector,
)

import uuid

from .models import CollectionName, Chunk
from .paths import QDRANT_DIR


def create_qdrant_client() -> QdrantClient:

    qdrant = QdrantClient(
        path=QDRANT_DIR,
    )

    return qdrant



def create_collections(
    client: QdrantClient,
    collections: list[str],
) -> None:

    existing = {
        c.name
        for c in client.get_collections().collections
    }

    for collection in collections:

        if collection in existing:
            print(f"{collection} already exists.")
            continue

        client.create_collection(
            collection_name=collection,

            vectors_config={
                "dense": VectorParams(
                    size=1024,
                    distance=Distance.COSINE,
                ),
            },

            sparse_vectors_config={
                "sparse": SparseVectorParams(),
            },
        )

        print(f"Created {collection}")



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

