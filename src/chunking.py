from __future__ import annotations

import math
import re


class FixedSizeChunker:
    """
    Split text into fixed-size chunks with optional overlap.

    Rules:
        - Each chunk is at most chunk_size characters long.
        - Consecutive chunks share overlap characters.
        - The last chunk contains whatever remains.
        - If text is shorter than chunk_size, return [text].
    """

    def __init__(self, chunk_size: int = 500, overlap: int = 50) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> list[str]:
        if not text:
            return []
        if len(text) <= self.chunk_size:
            return [text]

        step = self.chunk_size - self.overlap
        chunks: list[str] = []
        for start in range(0, len(text), step):
            chunk = text[start : start + self.chunk_size]
            chunks.append(chunk)
            if start + self.chunk_size >= len(text):
                break
        return chunks


class SentenceChunker:
    """
    Split text into chunks of at most max_sentences_per_chunk sentences.

    Sentence detection: split on ". ", "! ", "? " or ".\n".
    Strip extra whitespace from each chunk.
    """

    def __init__(self, max_sentences_per_chunk: int = 3) -> None:
        self.max_sentences_per_chunk = max(1, max_sentences_per_chunk)

    def chunk(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []

        # Split after sentence-ending punctuation so the punctuation remains in
        # the sentence. This intentionally keeps the rule simple for the lab;
        # abbreviations such as "Dr." may still be treated as sentence breaks.
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])(?:[ \t]+|\r?\n+)", text.strip())
            if sentence.strip()
        ]

        return [
            " ".join(sentences[start : start + self.max_sentences_per_chunk])
            for start in range(0, len(sentences), self.max_sentences_per_chunk)
        ]


class RecursiveChunker:
    """
    Recursively split text using separators in priority order.

    Default separator priority:
        ["\n\n", "\n", ". ", " ", ""]
    """

    DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

    def __init__(self, separators: list[str] | None = None, chunk_size: int = 500) -> None:
        self.separators = list(self.DEFAULT_SEPARATORS) if separators is None else list(separators)
        self.chunk_size = max(1, chunk_size)

    def chunk(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []
        return self._split(text, list(self.separators))

    def _split(self, current_text: str, remaining_separators: list[str]) -> list[str]:
        if not current_text or not current_text.strip():
            return []
        if len(current_text) <= self.chunk_size:
            return [current_text.strip()]

        # When no useful boundary remains, fall back to deterministic
        # fixed-size slicing. This is also the base case for separators=[].
        if not remaining_separators or remaining_separators[0] == "":
            return [
                piece.strip()
                for start in range(0, len(current_text), self.chunk_size)
                if (piece := current_text[start : start + self.chunk_size]).strip()
            ]

        separator = remaining_separators[0]
        next_separators = remaining_separators[1:]
        if separator not in current_text:
            return self._split(current_text, next_separators)

        raw_parts = current_text.split(separator)
        # Reattach the separator so punctuation and paragraph boundaries are
        # preserved when adjacent small parts are merged.
        parts = [
            part + (separator if index < len(raw_parts) - 1 else "")
            for index, part in enumerate(raw_parts)
            if part.strip()
        ]

        chunks: list[str] = []
        merge_buffer: list[str] = []

        def flush_buffer() -> None:
            if not merge_buffer:
                return
            merged = "".join(merge_buffer).strip()
            if merged:
                chunks.append(merged)
            merge_buffer.clear()

        for part in parts:
            if len(part) > self.chunk_size:
                flush_buffer()
                chunks.extend(self._split(part, next_separators))
                continue

            candidate = "".join([*merge_buffer, part])
            if merge_buffer and len(candidate) > self.chunk_size:
                flush_buffer()
            merge_buffer.append(part)

        flush_buffer()
        return chunks


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def compute_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    cosine_similarity = dot(a, b) / (||a|| * ||b||)

    Returns 0.0 if either vector has zero magnitude.
    """
    magnitude_a = math.sqrt(_dot(vec_a, vec_a))
    magnitude_b = math.sqrt(_dot(vec_b, vec_b))
    if magnitude_a == 0.0 or magnitude_b == 0.0:
        return 0.0
    return _dot(vec_a, vec_b) / (magnitude_a * magnitude_b)


class ChunkingStrategyComparator:
    """Run all built-in chunking strategies and compare their results."""

    def compare(self, text: str, chunk_size: int = 200) -> dict:
        safe_chunk_size = max(1, chunk_size)
        overlap = min(50, max(0, safe_chunk_size // 10))
        strategies = {
            "fixed_size": FixedSizeChunker(chunk_size=safe_chunk_size, overlap=overlap),
            "by_sentences": SentenceChunker(max_sentences_per_chunk=3),
            "recursive": RecursiveChunker(chunk_size=safe_chunk_size),
        }

        comparison: dict[str, dict] = {}
        for name, chunker in strategies.items():
            chunks = chunker.chunk(text)
            count = len(chunks)
            comparison[name] = {
                "count": count,
                "avg_length": sum(len(chunk) for chunk in chunks) / count if count else 0.0,
                "chunks": chunks,
            }
        return comparison
