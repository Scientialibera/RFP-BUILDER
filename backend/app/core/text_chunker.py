"""
Token-based chunking helpers for large RFP texts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

import tiktoken


PAGE_MARKER = "PAGE TO CITE:"


@dataclass(frozen=True)
class PageBlock:
    page_num: int
    text: str


def _get_encoding(model: str | None = None) -> tiktoken.Encoding:
    if model:
        try:
            return tiktoken.encoding_for_model(model)
        except KeyError:
            pass
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str, model: str | None = None) -> int:
    if not text:
        return 0
    enc = _get_encoding(model)
    return len(enc.encode(text))


def truncate_to_tokens(text: str, max_tokens: int, model: str | None = None) -> str:
    if max_tokens <= 0 or not text:
        return ""
    enc = _get_encoding(model)
    tokens = enc.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return enc.decode(tokens[:max_tokens])


def parse_pages(text: str) -> list[PageBlock]:
    pattern = re.compile(rf"{re.escape(PAGE_MARKER)}\s*(\d+)\s*\n", re.MULTILINE)
    parts = pattern.split(text)
    if len(parts) < 3:
        return []
    blocks: list[PageBlock] = []
    it = iter(parts)
    _ = next(it, "")
    while True:
        page_num = next(it, None)
        page_text = next(it, None)
        if page_num is None or page_text is None:
            break
        page_num_int = int(page_num)
        page_text = page_text.strip()
        block_text = f"{PAGE_MARKER} {page_num_int}\n{page_text}"
        blocks.append(PageBlock(page_num=page_num_int, text=block_text))
    return blocks


def chunk_pages_by_tokens(
    pages: Iterable[PageBlock],
    max_tokens: int,
    model: str | None = None,
) -> list[list[PageBlock]]:
    if max_tokens <= 0:
        return [list(pages)]
    enc = _get_encoding(model)
    chunks: list[list[PageBlock]] = []
    current: list[PageBlock] = []
    current_tokens = 0

    for page in pages:
        page_tokens = len(enc.encode(page.text))
        if current and current_tokens + page_tokens > max_tokens:
            chunks.append(current)
            current = []
            current_tokens = 0
        current.append(page)
        current_tokens += page_tokens

    if current:
        chunks.append(current)
    return chunks


def format_chunk_pages(pages: Iterable[PageBlock]) -> str:
    nums = [p.page_num for p in pages]
    if not nums:
        return "none"
    nums_sorted = sorted(nums)
    return ", ".join(str(n) for n in nums_sorted)
