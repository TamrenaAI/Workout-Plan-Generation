import asyncio
import time
from .models import Chunk, PrinciplesMetadata, GoalNamespaceMetadata
from langchain_core.language_models.chat_models import BaseChatModel
from .prompts import PRINCIPLES_METADATA_PROMPT, GOAL_METADATA_PROMPT
from pathlib import Path
from .storage import chunk_exists, load_chunk, save_chunk
from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from .models import GoalQueryFilter, PrinciplesQueryFilter
from .prompts import GOAL_QUERY_FILTER_PROMPT, PRINCIPLES_QUERY_FILTER_PROMPT



T = TypeVar("T")



def should_retry(error: Exception) -> bool:
    error_msg = str(error).lower()

    return any(
        token in error_msg
        for token in (
            "429",
            "503",
            "rate_limit",
            "resource",
            "timeout",
            "time out",
        )
    )


async def generate_metadata_async(chunk: Chunk, llm: BaseChatModel) -> Chunk:
    if chunk.collection == "principles":
        prompt = PRINCIPLES_METADATA_PROMPT
        schema = PrinciplesMetadata
    else:
        prompt = GOAL_METADATA_PROMPT
        schema = GoalNamespaceMetadata

    structured_llm = llm.with_structured_output(schema)
    chain = prompt | structured_llm

    while True:
        try:
            metadata = await chain.ainvoke(
                {
                    "collection": chunk.collection,
                    "book": chunk.book,
                    "chapter": chunk.chapter,
                    "text": chunk.text,
                }
            )
            break

        except Exception as e:
            if should_retry(e):
                print(f"[{chunk.id}] wait 60 sec")
                await asyncio.sleep(60)
                continue
            else:
                raise e

    return chunk.model_copy(update={"metadata": metadata})


async def generate_metadata_for_all_chunks_async(
    llm: BaseChatModel,
    chunks_dir: Path,
    max_concurrent_tasks: int = 10, 
) -> list[Chunk]:

    chunks_with_metadata = []
    tasks = []
    skipped_count = 0

    semaphore = asyncio.Semaphore(max_concurrent_tasks)

    chunk_paths = sorted(
        chunks_dir.glob("*.json")
    )



    for chunk_path in chunk_paths:

        chunk = load_chunk(chunk_path)
    
        if chunk.metadata is not None:
            chunks_with_metadata.append(chunk)
            skipped_count += 1
            continue
        
        tasks.append(generate_metadata_with_save_async(chunk, llm, chunks_dir, semaphore))

    if skipped_count > 0:
        print(f"Skipping {skipped_count} already processed chunks. ⏩")

    if not tasks:
        print("All chunks are already processed! 🎉")
        return chunks_with_metadata

    print(f"Starting controlled parallel processing for {len(tasks)} chunks (Max {max_concurrent_tasks} at a time)... 🚀")

    processed_chunks = await asyncio.gather(*tasks)

    chunks_with_metadata.extend(processed_chunks)
    
    print(f"Done! All {len(chunks_with_metadata)} chunks are now ready. ✅")
    return chunks_with_metadata


async def generate_metadata_with_save_async(
    chunk: Chunk, 
    llm: BaseChatModel, 
    chunks_dir: Path,
    semaphore: asyncio.Semaphore
) -> Chunk:
    
    async with semaphore:
        updated_chunk = await generate_metadata_async(chunk=chunk, llm=llm)
        
        save_chunk(chunk=updated_chunk, chunks_dir=chunks_dir)
        
        return updated_chunk
    

class BaseMetadataExtractor(ABC, Generic[T]):

    @abstractmethod
    def extract(
        self,
        query: str,
    ) -> T:
        """
        Extract metadata from a user query.
        """
        pass



class GoalMetadataExtractor(
    BaseMetadataExtractor[GoalQueryFilter]
):

    def __init__(
        self,
        llm: BaseChatModel,
    ):
        self.chain = (
            GOAL_QUERY_FILTER_PROMPT
            | llm.with_structured_output(GoalQueryFilter)
        )

        self._cache: dict[str, GoalQueryFilter] = {}

    def extract(
        self,
        query: str,
    ) -> GoalQueryFilter:

        if query in self._cache:
            return self._cache[query]

        metadata = self.chain.invoke(
            {
                "query": query,
            }
        )

        self._cache[query] = metadata

        return metadata

class PrinciplesMetadataExtractor(
    BaseMetadataExtractor[PrinciplesQueryFilter]
):

    def __init__(
        self,
        llm: BaseChatModel,
    ):
        self.chain = (
            PRINCIPLES_QUERY_FILTER_PROMPT
            | llm.with_structured_output(PrinciplesQueryFilter)
        )

        self._cache: dict[str, PrinciplesQueryFilter] = {}

    def extract(
        self,
        query: str,
    ) -> PrinciplesQueryFilter:

        if query in self._cache:
            return self._cache[query]

        metadata = self.chain.invoke(
            {
                "query": query,
            }
        )

        self._cache[query] = metadata

        return metadata

    