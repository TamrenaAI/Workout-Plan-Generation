from pathlib import Path
import re

from itertools import islice
from collections.abc import Iterator


def slugify(text: str) -> str:
    text = text.lower().strip()

    text = re.sub(r"[^\w\s-]", "", text)

    text = re.sub(r"[-\s]+", "_", text)

    return text




def batch_iterator(
    items: list,
    batch_size: int,
) -> Iterator[list]:

    iterator = iter(items)

    while batch := list(islice(iterator, batch_size)):
        yield batch


