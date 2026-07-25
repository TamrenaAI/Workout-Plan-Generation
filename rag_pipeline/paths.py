from pathlib import Path
from rag_pipeline.models import BookPaths


PROJECT_ROOT = Path(__file__).resolve().parent.parent

ASSETS_DIR = PROJECT_ROOT / "assets"
MODELS_DIR = ASSETS_DIR / "models"
FASTEMBED_DIR = MODELS_DIR / "fastembed"
DENSE_DIR = MODELS_DIR / "all-MiniLM-L6-v2"
RERANKER_DIR = MODELS_DIR / "jina-reranker-v1-tiny-en"
RAG_DATA_DIR = PROJECT_ROOT / "rag_data"

BOOKS_DIR = RAG_DATA_DIR / "books"
QDRANT_DIR = RAG_DATA_DIR / "qdrant"




def get_book_paths(book_name: str) -> BookPaths:
    book_dir = BOOKS_DIR / book_name

    return BookPaths(
        book_dir=book_dir,
        chapters_dir=book_dir / "chapters",
        markdown_dir=book_dir / "markdown",
        chunks_dir=book_dir / "chunks",
    )

