import json
from pathlib import Path
from .models import Chunk
from tqdm.auto import tqdm


def save_chunk(
    chunk: Chunk,
    chunks_dir: Path,
) -> None:

    path = chunks_dir / f"{chunk.id}.json"

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            chunk.model_dump(),
            f,
            ensure_ascii=False,
            indent=2,
        )

def load_chunk(
    path: Path,
) -> Chunk:

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return Chunk.model_validate(data)

def chunk_exists(
    chunk: Chunk,
    chunks_dir: Path,
) -> bool:

    return (chunks_dir / f"{chunk.id}.json").exists()

def save_chunks(
    chunks: list[Chunk],
    chunks_dir: Path,
) -> None:
    for chunk in chunks:
        save_chunk(
            chunk=chunk,
            chunks_dir=chunks_dir,
        )


def load_all_chunks(
    chunks_dir: Path,
) -> list[Chunk]:

    chunk_paths = sorted(
        chunks_dir.glob("*.json")
    )

    return [
        load_chunk(path)
        for path in tqdm(chunk_paths)
    ]
