import argparse
import asyncio
from pathlib import Path

from rag_pipeline.llms import (
    LLMConfig,
    LLMProvider,
    create_llm,
)

from rag_pipeline.metadata import (
    generate_metadata_for_all_chunks_async,
)

from rag_pipeline.paths import get_book_paths



# LLM_CONFIG = LLMConfig(
#     provider=LLMProvider.NVIDIA,
#     model="nvidia/nemotron-3-super-120b-a12b",
# )

LLM_CONFIG = LLMConfig(
    provider=LLMProvider.GROQ,
    model="openai/gpt-oss-120b",
)

# LLM_CONFIG = LLMConfig(
#    provider=LLMProvider.GEMINI,
#    model="models/gemini-2.5-flash"
# )

# LLM_CONFIG = LLMConfig(
#     provider=LLMProvider.OPENROUTER,
#     model="nvidia/nemotron-3-ultra-550b-a55b:free",
#     temperature=0
# )

# LLM_CONFIG = LLMConfig(
#     provider=LLMProvider.ITI,
#     model="anthropic.claude-sonnet-4-6",
#     temperature=0
# )



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate metadata for chunks."
    )

    parser.add_argument(
        "book_name",
        help="Book directory name.",
    )

    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=5,
        help="Maximum concurrent metadata requests.",
    )

    return parser.parse_args()


async def main() -> None:

    args = parse_args()

    paths = get_book_paths(args.book_name)

    llm = create_llm(LLM_CONFIG)

    await generate_metadata_for_all_chunks_async(
        llm=llm,
        chunks_dir=paths.chunks_dir,
        max_concurrent_tasks=args.max_concurrent,
    )

    print("Metadata generation completed.")


if __name__ == "__main__":
    asyncio.run(main())

