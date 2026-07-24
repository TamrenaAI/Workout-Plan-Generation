import fitz
from .models import BookInfo, BookPaths, ChapterInfo, Chunk, CollectionName
from .utils import slugify
from pathlib import Path
import re
from collections import defaultdict


def _title_from_first_page(doc: fitz.Document) -> str:
    if doc.page_count == 0:
        return ""

    page = doc[0]
    blocks = page.get_text("dict")["blocks"]

    candidates = []  # (height, text)

    for block in blocks:
        if block.get("type") != 0:  
            continue
        for line in block.get("lines", []):
            text = "".join(span["text"] for span in line["spans"]).strip()
            if not text or len(text) < 3:
                continue
            bbox = line["bbox"]  # (x0, y0, x1, y1)
            height = bbox[3] - bbox[1]  
            candidates.append((height, text))

    if not candidates:
        return ""

    candidates.sort(key=lambda c: c[0], reverse=True)
    return candidates[0][1]

def _title_from_filename(pdf_path: str) -> str:
    stem = Path(pdf_path).stem
    stem = re.sub(r"[_\-]+", " ", stem)
    return stem.strip().title()


def extract_book_info(pdf_path: str) -> BookInfo:
    doc = fitz.open(pdf_path)
    metadata = doc.metadata

    title = (metadata.get("title") or "").strip()
    author = (metadata.get("author") or "").strip().rstrip(";")

    source = "metadata"

    if not title:
        title = _title_from_first_page(doc)
        source = "first_page"

    if not title:
        title = _title_from_filename(pdf_path)
        source = "filename"

    doc.close()

    return BookInfo(
        title=title,
        author=author,
        slug=slugify(title),
    )



def create_book_folders(
    root_dir: Path,
    book: BookInfo,
) -> BookPaths:
    """
    Create the folder structure for a book.

    Structure:
    data/
    └── books/
        └── <book_slug>/
            ├── chapters/
            └── markdown/
    """

    book_dir = root_dir / book.slug

    chapters_dir = book_dir / "chapters"
    markdown_dir = book_dir / "markdown"
    chunks_dir = book_dir / "chunks"


    chapters_dir.mkdir(parents=True, exist_ok=True)
    markdown_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir.mkdir(parents=True, exist_ok=True)

    return BookPaths(
        book_dir=book_dir,
        chapters_dir=chapters_dir,
        markdown_dir=markdown_dir,
        chunks_dir=chunks_dir,
    )



def extract_chapter(
    pdf_path: Path,
    start_page: int,
    end_page: int,
    output_path: Path,
)-> None:
    src = fitz.open(pdf_path)
    dst = fitz.open()

    # fitz uses zero-based indexing
    dst.insert_pdf(
        src,
        from_page=start_page - 1,
        to_page=end_page - 1,
    )

    dst.save(output_path)
    dst.close()
    src.close()

def extract_all_chapters(
    pdf_path: Path,
    chapters: list[ChapterInfo],
    chapters_dir: Path,
) -> list[Path]:
    
    chapter_paths = []

    for index, chapter in enumerate(chapters, start=1):

        output_path = chapters_dir / f"chapter_{index:02d}.pdf"

        extract_chapter(
            pdf_path=pdf_path,
            start_page=chapter.start_page,
            end_page=chapter.end_page,
            output_path=output_path,
        )
        chapter_paths.append(output_path)

    return chapter_paths




def _chapters_from_toc(doc: fitz.Document, toc: list) -> list[ChapterInfo]:
    chapters = []
    for i, (_, title, start_page) in enumerate(toc):
        if not title.lower().strip().startswith("chapter"):
            continue

        if i + 1 < len(toc):
            end_page = toc[i + 1][2] - 1
        else:
            end_page = doc.page_count

        chapters.append(ChapterInfo(title=title.strip(), start_page=start_page, end_page=end_page))
    return chapters


def _chapters_from_text(doc: fitz.Document, min_font_size: float = 20.0) -> list[ChapterInfo]:
    chapter_pattern = re.compile(r"^chapter\b", re.IGNORECASE)

    matches = []  # (page_number, title, font_size)

    for page_num in range(doc.page_count):
        page = doc[page_num]
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            for line in block.get("lines", []):
                line_text = "".join(span["text"] for span in line["spans"]).strip()
                if not chapter_pattern.match(line_text):
                    continue
                max_size = max(span["size"] for span in line["spans"])
                if max_size >= min_font_size:
                    matches.append((page_num + 1, line_text, max_size))

    chapters = []
    for i, (start_page, title, _) in enumerate(matches):
        end_page = matches[i + 1][0] - 1 if i + 1 < len(matches) else doc.page_count
        chapters.append(ChapterInfo(title=title.strip(), start_page=start_page, end_page=end_page))
    return chapters



def extract_chapters_info(pdf_path: Path) -> list[ChapterInfo]:
    doc = fitz.open(pdf_path)
    toc = doc.get_toc()

    chapters = _chapters_from_toc(doc, toc) if toc else []

    if not chapters:
        chapters = _chapters_from_text(doc)

    doc.close()
    return chapters

def group_chunks_by_collection(
    chunks: list[Chunk],
) -> dict[CollectionName, list[Chunk]]:

    chunks_by_collection = defaultdict(list)

    for chunk in chunks:
        chunks_by_collection[chunk.collection].append(chunk)

    return chunks_by_collection

def build_corpus_by_collection(
    grouped_chunks: dict[CollectionName, list[Chunk]],
) -> dict[CollectionName, list[str]]:
    return {
        collection: [
            chunk.text
            for chunk in chunks
        ]
        for collection, chunks in grouped_chunks.items()
    }

