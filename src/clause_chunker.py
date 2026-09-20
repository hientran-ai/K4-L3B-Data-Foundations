from __future__ import annotations

import re

from .chunking import RecursiveChunker


class ClauseChunker:
    """Split policy text at Markdown headings and numbered clauses.

    This strategy targets legal/policy documents whose answer units often
    start with markers such as ``1.``, ``1.2.``, ``a.`` or ``ii.``. Long
    clauses fall back to RecursiveChunker so every chunk respects max_chars.
    """

    CLAUSE_START = re.compile(
        r"^\s*(?:#{1,6}\s+|\d+(?:\.\d+)*\.?\s+|[A-Za-z]\.\s+|"
        r"(?:i|ii|iii|iv|v|vi|vii|viii|ix|x)\.\s+)",
        re.IGNORECASE,
    )

    def __init__(self, max_chars: int = 400) -> None:
        self.max_chars = max(1, max_chars)

    def _split_long(self, text: str) -> list[str]:
        if len(text) <= self.max_chars:
            return [text]
        return RecursiveChunker(chunk_size=self.max_chars).chunk(text)

    def chunk(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []

        chunks: list[str] = []
        current: list[str] = []
        for line in text.splitlines():
            if self.CLAUSE_START.match(line) and any(part.strip() for part in current):
                chunks.extend(self._split_long("\n".join(current).strip()))
                current = []
            current.append(line)

        if any(part.strip() for part in current):
            chunks.extend(self._split_long("\n".join(current).strip()))
        return [chunk for chunk in chunks if chunk.strip()]
