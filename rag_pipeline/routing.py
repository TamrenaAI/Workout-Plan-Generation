from langchain_core.language_models import BaseChatModel
from .models import CollectionRoute
from .prompts import ROUTING_PROMPT
from pathlib import Path
from .markdown import load_markdown

def route_chapter(
    markdown: str,
    llm: BaseChatModel,
) -> CollectionRoute:

    structured_llm = llm.with_structured_output(CollectionRoute, method="json_mode",)

    chain = ROUTING_PROMPT | structured_llm

    return chain.invoke(
        {
            "chapter": markdown,
        }
    )

def prepare_chapter_for_routing(markdown: str) -> str:

    chapter_title = None
    section_titles = []

    for line in markdown.splitlines():

        line = line.strip()

        if line.startswith("# "):
            chapter_title = line.removeprefix("# ").strip()

        elif line.startswith("## "):
            section_titles.append(
                line.removeprefix("## ").strip()
            )

    if chapter_title is None:
        raise ValueError(
            "No chapter title found."
        )

    result = [
        chapter_title,
        "",
        "Sections:",
    ]

    result.extend(
        f"- {section}"
        for section in section_titles
    )

    return "\n".join(result)


def route_all_chapters(
    markdown_paths: list[Path],
    llm,
) -> dict[str, CollectionRoute]:

    routes = {}

    for markdown_path in markdown_paths:

        markdown = load_markdown(markdown_path)

        routing_input = prepare_chapter_for_routing(
            markdown
        )

        route = route_chapter(
            markdown=routing_input,
            llm=llm,
        )

        routes[markdown_path.name] = route

    return routes
