from langchain_text_splitters import RecursiveCharacterTextSplitter
from pathlib import Path
from .models import CollectionRoute, BookInfo, ChunkingConfig, Chunk
from .markdown import load_markdown

def extract_chapter_title(
    markdown: str,
) -> str:

    for line in markdown.splitlines():

        line = line.strip()

        if line.startswith("# "):
            return line.removeprefix("# ").strip()

    raise ValueError(
        "Chapter title not found."
    )

def create_text_splitter(config: ChunkingConfig):
    return RecursiveCharacterTextSplitter(
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        separators=config.separators,
    )

def chunk_markdown(
    markdown: str,
    markdown_path: Path,
    chapter_routes: dict[str, CollectionRoute],
    book_info: BookInfo,
    config: ChunkingConfig,
) -> list[Chunk]:

    chapter = extract_chapter_title(
        markdown,
    )

    collection = chapter_routes[
        markdown_path.name
    ].collection

    splitter = create_text_splitter(config=config)

    texts = splitter.split_text(
        markdown,
    )

    merged = []

    for text in texts:
        if len(text) < config.min_chunk_chars and merged:
            merged[-1] += "\n\n" + text
        else:
            merged.append(text)

    texts = merged


    return [
        Chunk(
            id="",
            text=text,
            book=book_info.title,
            chapter=chapter,
            collection=collection,
            chunk_index=i,
        )
        for i, text in enumerate(texts)
    ]

def assign_chunk_ids(
    chunks: list[Chunk],
    book_slug: str,
) -> None:
    for i, chunk in enumerate(chunks):
        chunk.id = f"{book_slug}_{i:06d}"


def chunk_all_chapters(
    markdown_paths: list[Path],
    chapter_routes: dict[str, CollectionRoute],
    book_info: BookInfo,
    config: ChunkingConfig,
) -> list[Chunk]:

    all_chunks = []

    for markdown_path in markdown_paths:

        markdown = load_markdown(
            markdown_path,
        )

        all_chunks.extend(
            chunk_markdown(
                markdown=markdown,
                markdown_path=markdown_path,
                chapter_routes=chapter_routes,
                book_info=book_info,
                config=config,
            )
        )
    
    assign_chunk_ids(
        chunks=all_chunks,
        book_slug=book_info.slug,
    )

    return all_chunks


