from __future__ import annotations

import re

from .chunking import RecursiveChunker


class HeadingChunker:
    """Split policy documents by Markdown or numbered section headings.

    The heading hierarchy is repeated in every emitted chunk. Oversized
    sections fall back to RecursiveChunker while retaining that hierarchy.
    """

    MARKDOWN_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
    NUMBERED_HEADING = re.compile(r"^(\d+(?:\.\d+)*\.)\s+(.+?)\s*$")
    LETTERED_HEADING = re.compile(r"^([A-Za-z])\.\s+(.+?)\s*$")

    def __init__(self, chunk_size: int = 500) -> None:
        self.chunk_size = max(1, chunk_size)

    def _heading(self, line: str) -> tuple[int, str] | None:
        stripped = line.strip()
        markdown_match = self.MARKDOWN_HEADING.match(stripped)
        if markdown_match:
            return len(markdown_match.group(1)), stripped

        numbered_match = self.NUMBERED_HEADING.match(stripped)
        if numbered_match:
            # Long numbered clauses (for example, "3.2. Người Mua có thể...")
            # contain policy facts rather than acting as section labels. Keep
            # them in the body so their content is not discarded when the next
            # numbered clause begins.
            if len(stripped) > 120:
                return None
            number = numbered_match.group(1).rstrip(".")
            return min(6, number.count(".") + 2), f"{'#' * min(6, number.count('.') + 2)} {stripped}"

        lettered_match = self.LETTERED_HEADING.match(stripped)
        if lettered_match:
            if len(stripped) > 100:
                return None
            return 4, f"#### {stripped}"
        return None

    def _emit_section(self, headings: list[str], body_lines: list[str]) -> list[str]:
        body = "\n".join(body_lines).strip()
        prefix = "\n".join(heading for heading in headings if heading).strip()
        if not body:
            return []

        section = f"{prefix}\n\n{body}".strip() if prefix else body
        if len(section) <= self.chunk_size:
            return [section]

        available_size = self.chunk_size - len(prefix) - 2
        if available_size <= 0:
            return RecursiveChunker(chunk_size=self.chunk_size).chunk(section)

        body_chunks = RecursiveChunker(chunk_size=available_size).chunk(body)
        return [
            f"{prefix}\n\n{chunk}".strip()
            for chunk in body_chunks
            if chunk.strip()
        ]

    def chunk(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []

        headings: list[str] = []
        body_lines: list[str] = []
        chunks: list[str] = []
        found_heading = False

        for line in text.splitlines():
            heading_info = self._heading(line)
            if heading_info is None:
                body_lines.append(line)
                continue

            found_heading = True
            if any(line.strip() for line in body_lines):
                chunks.extend(self._emit_section(headings, body_lines))
                body_lines = []

            level, normalized_heading = heading_info
            headings = headings[: level - 1]
            while len(headings) < level - 1:
                headings.append("")
            headings.append(normalized_heading)

        if any(line.strip() for line in body_lines):
            chunks.extend(self._emit_section(headings, body_lines))

        if not found_heading or not chunks:
            return RecursiveChunker(chunk_size=self.chunk_size).chunk(text)
        return chunks
