from dataclasses import dataclass
from typing import Type

from sentence_transformers import SentenceTransformer, CrossEncoder


@dataclass(frozen=True)
class ModelSpec:
    model_class: Type
    huggingface_name: str


MODELS = {
    "bge-m3": ModelSpec(
        model_class=SentenceTransformer,
        huggingface_name="BAAI/bge-m3",
    ),
    "bge-reranker-v2-m3": ModelSpec(
        model_class=CrossEncoder,
        huggingface_name="BAAI/bge-reranker-v2-m3",
    ),
    "jina-reranker-v1-tiny-en": ModelSpec(
        model_class=CrossEncoder,
        huggingface_name="jinaai/jina-reranker-v1-tiny-en"
    ),
    "all-MiniLM-L6-v2": ModelSpec(
        model_class=SentenceTransformer,
        huggingface_name="all-MiniLM-L6-v2"
    )
}
