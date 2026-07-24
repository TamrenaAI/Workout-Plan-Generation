from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from pathlib import Path
from copy import deepcopy
from typing import Iterable
from .models import ChapterInfo
import re


def create_converter() -> DocumentConverter:
    pipeline_options = PdfPipelineOptions()

    pipeline_options.do_ocr = False
    pipeline_options.do_table_structure = False
    pipeline_options.do_picture_description = False
    pipeline_options.do_picture_classification = False

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options
            )
        }
    )



def convert_pdf(
    converter: DocumentConverter,
    pdf_path: Path,
):
    result = converter.convert(pdf_path)

    return result.document


ALLOWED_LABELS = {
    "section_header",
    "text",
    "list_item",
}


def keep_labels(doc, allowed_labels: Iterable[str]):
    """
    Return a copy of a DoclingDocument keeping only the specified labels.

    Parameters
    ----------
    doc : DoclingDocument
        Original document.

    allowed_labels : Iterable[str]
        Labels to keep.
        Example:
            {
                "section_header",
                "text",
                "list_item",
            }

    Returns
    -------
    DoclingDocument
        Filtered copy of the document.
    """

    doc = deepcopy(doc)

    allowed_labels = {label.lower() for label in allowed_labels}

    items_to_delete = []

    for item, _ in doc.iterate_items():
        label = str(getattr(item, "label", "")).lower()

        if label not in allowed_labels:
            items_to_delete.append(item)

    if items_to_delete:
        doc.delete_items(node_items=items_to_delete)

    return doc


def add_chapter_title(
    markdown: str,
    chapter_title: str,
) -> str:

    return f"# {chapter_title}\n\n{markdown}"

def save_markdown(markdown: str, output_path: Path) -> None:

    output_path = Path(output_path)

    output_path.write_text(
        markdown,
        encoding="utf-8",
    )


def load_markdown(markdown_path: Path) -> str:
    return markdown_path.read_text(encoding="utf-8")


def convert_all_chapters_to_markdown(
    converter: DocumentConverter,
    chapter_infos: list[ChapterInfo],
    chapter_paths: list[Path],
    markdown_dir: Path,
) -> list[Path]:

    markdown_paths = []

    for chapter, chapter_path in zip(
        chapter_infos,
        chapter_paths,
    ):

        doc = convert_pdf(
            converter=converter,
            pdf_path=chapter_path,
        )

        doc = keep_labels(
            doc,
            ALLOWED_LABELS,
        )

        markdown = doc.export_to_markdown()

        markdown = add_chapter_title(
            markdown=markdown,
            chapter_title=chapter.title,
        )

        markdown_path = (
            markdown_dir /
            f"{chapter_path.stem}.md"
        )

        save_markdown(
            markdown=markdown,
            output_path=markdown_path,
        )

        markdown_paths.append(markdown_path)

    return markdown_paths


def normalize_title(title: str) -> str:

    title = re.sub(
        r"^Chapter\s+\d+\s*:\s*",
        "",
        title,
        flags=re.IGNORECASE,
    )

    return title.strip().casefold()


def remove_duplicate_chapter_title(
    markdown: str,
) -> str:

    lines = markdown.splitlines()

    if not lines:
        return markdown

    if not lines[0].startswith("# "):
        return markdown

    chapter_title = normalize_title(
        lines[0].removeprefix("# ")
    )

    for i in range(1, len(lines)):

        line = lines[i].strip()

        if not line:
            continue

        if line.startswith("## "):

            section_title = normalize_title(
                line.removeprefix("## ")
            )

            if section_title == chapter_title:
                del lines[i]

            break

        break

    return "\n".join(lines)


def clean_markdown(markdown: str) -> str:

    markdown = markdown.strip()

    markdown = remove_duplicate_chapter_title(
        markdown,
    )

    # Remove figure/image IDs
    markdown = re.sub(
        r"E\d+/[^\n]+",
        "",
        markdown,
    )

    # Remove figure references
    markdown = re.sub(
        r"\b[Ff]igure\s+\d+(?:\.\d+)?\b",
        "",
        markdown,
    )

    # Remove table references
    markdown = re.sub(
        r"\b[Tt]able\s+\d+(?:\.\d+)?\b",
        "",
        markdown,
    )

    # Remove page labels (e.g. "1 chapter")
    markdown = re.sub(
        r"^\d+\s+chapter\s*$",
        "",
        markdown,
        flags=re.MULTILINE,
    )
    
    # Collapse multiple spaces
    markdown = re.sub(
        r"[ \t]{2,}",
        " ",
        markdown,
    )

    # Collapse multiple blank lines
    markdown = re.sub(
        r"\n{3,}",
        "\n\n",
        markdown,
    )

    markdown = re.sub(
        r"\s*\(continued\)",
        "",
        markdown,
        flags=re.IGNORECASE,
    )

    markdown = re.sub(
        r"(\w)-\n(\w)",
        r"\1\2",
        markdown,
    )

    markdown = re.sub(
        r"[ \t]+\n",
        "\n",
        markdown,
    )

    return markdown

def clean_all_markdown(
    markdown_paths: list[Path],
) -> None:

    for markdown_path in markdown_paths:

        markdown = load_markdown(markdown_path)

        markdown = clean_markdown(markdown)

        save_markdown(
            markdown,
            markdown_path,
        )

