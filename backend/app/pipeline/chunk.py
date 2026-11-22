import re
from functools import lru_cache

import tiktoken

from app.pipeline.models import PageChunk, PageText

_ENCODING_NAME = "cl100k_base"


@lru_cache(maxsize=1)
def _encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding(_ENCODING_NAME)


def count_tokens(text: str) -> int:
    return len(_encoding().encode(text, disallowed_special=()))


def chunk_pages(pages: list[PageText], token_budget: int) -> list[PageChunk]:
    chunks: list[PageChunk] = []
    for page in pages:
        for piece in _split(page.text.strip(), token_budget):
            chunks.append(PageChunk(page=page.page, text=piece, token_count=count_tokens(piece)))
    return chunks


def _split(text: str, budget: int) -> list[str]:
    if not text:
        return []
    if count_tokens(text) <= budget:
        return [text]
    return _pack(_units(text, budget), budget, "\n\n")


def _units(text: str, budget: int) -> list[str]:
    units: list[str] = []
    for paragraph in text.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if count_tokens(paragraph) <= budget:
            units.append(paragraph)
            continue
        units.extend(_pack(_sentences(paragraph, budget), budget, " "))
    return units


def _sentences(paragraph: str, budget: int) -> list[str]:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", paragraph) if part.strip()]
    units: list[str] = []
    for sentence in sentences:
        if count_tokens(sentence) <= budget:
            units.append(sentence)
            continue
        units.extend(_windows(sentence, budget))
    return units


def _windows(text: str, budget: int) -> list[str]:
    encoding = _encoding()
    tokens = encoding.encode(text, disallowed_special=())
    return [
        encoding.decode(tokens[start : start + budget]) for start in range(0, len(tokens), budget)
    ]


def _pack(units: list[str], budget: int, separator: str) -> list[str]:
    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = unit if not current else f"{current}{separator}{unit}"
        if current and count_tokens(candidate) > budget:
            chunks.append(current)
            current = unit
            continue
        current = candidate
    if current:
        chunks.append(current)
    return chunks
