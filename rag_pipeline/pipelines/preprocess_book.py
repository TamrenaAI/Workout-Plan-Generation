from pathlib import Path
import argparse

from rag_pipeline.chunking import ChunkingConfig, chunk_all_chapters
from rag_pipeline.llms import LLMConfig, LLMProvider, create_llm
from rag_pipeline.markdown import (
    clean_all_markdown,
    convert_all_chapters_to_markdown,
    create_converter,
)
from rag_pipeline.preprocessing import (
    create_book_folders,
    extract_all_chapters,
    extract_book_info,
    extract_chapters_info,
)
from rag_pipeline.routing import route_all_chapters
from rag_pipeline.storage import save_chunks
from rag_pipeline.paths import BOOKS_DIR


LLM_CONFIG = LLMConfig(
    provider=LLMProvider.GROQ,
    model="openai/gpt-oss-120b",
)

CHUNKING_CONFIG = ChunkingConfig()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preprocess a book into chunks."
    )

    parser.add_argument(
        "book",
        type=Path,
        help="Path to the PDF book.",
    )

    parser.add_argument(
        "--data-dir",
        type=Path,
        default=BOOKS_DIR,
        help="Directory to store processed data.",
    )

    return parser.parse_args()

def main():
    args = parse_args()

    llm = create_llm(LLM_CONFIG)

    book = extract_book_info(args.book)
    print(book)


    paths = create_book_folders(
        root_dir=args.data_dir,
        book=book,
    )

    chapter_infos = extract_chapters_info(args.book)

    chapter_paths = extract_all_chapters(
        pdf_path=args.book,
        chapters=chapter_infos,
        chapters_dir=paths.chapters_dir,
    )


    converter = create_converter()

    markdown_paths = convert_all_chapters_to_markdown(
        converter=converter,
        chapter_infos=chapter_infos,
        chapter_paths=chapter_paths,
        markdown_dir=paths.markdown_dir,
    )

    clean_all_markdown(markdown_paths)

    chapter_routes = route_all_chapters(
        markdown_paths=markdown_paths,
        llm=llm,
    )
    print(chapter_routes)

    chunks = chunk_all_chapters(
        markdown_paths=markdown_paths,
        chapter_routes=chapter_routes,
        book_info=book,
        config=CHUNKING_CONFIG,
    )

    save_chunks(
        chunks=chunks,
        chunks_dir=paths.chunks_dir,
    )

    print(f"Book: {book.title}")
    print(f"Collection folders: {paths.book_dir}")
    print(f"Generated {len(chunks)} chunks.")
    print(f"Chunks saved to: {paths.chunks_dir}")

if __name__ == "__main__":
    main()