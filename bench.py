from __future__ import annotations

import argparse
import hashlib
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src import (
    ClauseChunker,
    Document,
    EmbeddingStore,
    FixedSizeChunker,
    GeminiEmbedder,
    HeadingChunker,
    LocalEmbedder,
    MockEmbedder,
    OpenAIEmbedder,
    RecursiveChunker,
)


TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)
SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+|\n+")
STOP_WORDS = {
    "bị", "bao", "bằng", "các", "có", "của", "cho", "được", "gì", "khi",
    "là", "một", "người", "những", "phải", "sau", "sản", "theo", "thì",
    "trong", "trên", "từ", "và", "về", "với",
}


BENCHMARKS: list[dict[str, Any]] = [
    {
        "query": "Bảo hành sản phẩm thông qua Shopee mất bao lâu?",
        "metadata_filter": {"audience": "buyer"},
        "gold_answer": "Dự kiến từ 20 đến 45 ngày làm việc, tính từ lúc Shopee nhận được sản phẩm.",
        "gold_doc_id": "shopee-chinh-sach-bao-hanh-san-pham",
        "markers": ["20 ngày", "45 ngày làm việc"],
    },
    {
        "query": "Sản phẩm cần thỏa những điều kiện gì để được bảo hành miễn phí?",
        "metadata_filter": {"audience": "buyer"},
        "gold_answer": (
            "Lỗi kỹ thuật do nhà sản xuất; còn trong thời hạn bảo hành; có hóa đơn điện tử "
            "hoặc mã đơn hàng; phiếu/tem bảo hành còn nguyên vẹn đối với đồ điện gia dụng."
        ),
        "gold_doc_id": "shopee-chinh-sach-bao-hanh-san-pham",
        "markers": [
            "lỗi kỹ thuật do nhà sản xuất",
            "còn trong thời hạn bảo hành",
            "mã đơn hàng",
            "tem bảo hành",
        ],
    },
    {
        "query": "Thời hạn gửi yêu cầu Trả hàng/Hoàn tiền với từng loại đơn hàng là bao lâu?",
        "metadata_filter": {"audience": "buyer"},
        "gold_answer": (
            "Đơn thông thường: 15 ngày sau khi giao thành công; thực phẩm tươi sống/đông lạnh: "
            "24 giờ; nếu chưa bấm Đã nhận được hàng: 20 ngày từ lúc lấy hàng thành công."
        ),
        "gold_doc_id": "shopee-quy-dinh-chung-tra-hang-hoan-tien",
        "markers": ["15 ngày", "24 giờ", "20 ngày"],
    },
    {
        "query": "Người bán được đăng bán hàng hóa còn bao nhiêu hạn sử dụng?",
        "metadata_filter": {"audience": "seller"},
        "gold_answer": "Còn ít nhất 30% thời hạn sử dụng và ít nhất 30 ngày đến ngày hết hạn.",
        "gold_doc_id": "shopee-quy-dinh-dang-ban-san-pham",
        "markers": ["ít nhất 30%", "ít nhất 30 ngày"],
    },
    {
        "query": "Thời hạn xử lý yêu cầu trả hàng/hoàn tiền là bao lâu?",
        "compare_without_filter": True,
        "variants": [
            {
                "label": "buyer",
                "metadata_filter": {"audience": "buyer"},
                "gold_answer": "Người mua có thể gửi yêu cầu trong vòng 15 ngày kể từ khi giao hàng thành công.",
                "gold_doc_id": "shopee-chinh-sach-tra-hang-hoan-tien-nguoi-mua",
                "markers": ["15 (mười lăm) ngày"],
            },
            {
                "label": "seller",
                "metadata_filter": {"audience": "seller"},
                "gold_answer": "Người bán cần phản hồi trong vòng 02 ngày lịch kể từ khi nhận thông báo.",
                "gold_doc_id": "shopee-chinh-sach-tra-hang-hoan-tien-nguoi-ban",
                "markers": ["02 ngày lịch"],
            },
        ],
    },
]


class LexicalHashEmbedder:
    """Dependency-free lexical vectorizer for a reproducible local benchmark."""

    def __init__(self, dim: int = 4096) -> None:
        self.dim = dim
        self._backend_name = "lexical hash (unigram + bigram)"

    def _tokens(self, text: str) -> list[str]:
        return [
            token
            for token in TOKEN_PATTERN.findall(text.casefold())
            if token not in STOP_WORDS and len(token) > 1
        ]

    def __call__(self, text: str) -> list[float]:
        tokens = self._tokens(text)
        features = tokens + [f"{left}_{right}" for left, right in zip(tokens, tokens[1:])]
        counts = Counter(features)
        vector = [0.0] * self.dim
        for feature, count in counts.items():
            digest = hashlib.md5(feature.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dim
            vector[index] += 1.0 + math.log(count)
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        return {"doc_id": path.stem}, raw

    parts = raw.split("---", 2)
    if len(parts) != 3:
        raise ValueError(f"Invalid frontmatter in {path}")

    metadata: dict[str, str] = {}
    for line in parts[1].splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")
    metadata.setdefault("doc_id", path.stem)
    return metadata, parts[2].strip()


def section_path(chunk: str) -> str:
    headings = [
        line.lstrip("#").strip()
        for line in chunk.splitlines()
        if re.match(r"^#{1,6}\s+", line)
    ]
    return " > ".join(headings)


def make_embedder(provider: str) -> Any:
    load_dotenv(override=False)
    if provider == "openai":
        return OpenAIEmbedder(
            model_name=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        )
    if provider == "gemini":
        return GeminiEmbedder(
            model_name=os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
        )
    if provider == "local":
        return LocalEmbedder()
    if provider == "mock":
        return MockEmbedder()
    return LexicalHashEmbedder()


def make_chunker(strategy: str, chunk_size: int) -> Any:
    if strategy == "fixed":
        return FixedSizeChunker(chunk_size=chunk_size, overlap=min(50, chunk_size - 1))
    if strategy == "recursive":
        return RecursiveChunker(chunk_size=chunk_size)
    if strategy == "clause":
        return ClauseChunker(max_chars=chunk_size)
    return HeadingChunker(chunk_size=chunk_size)


def build_store(
    data_dir: Path,
    chunk_size: int,
    strategy: str = "heading",
    provider: str = "lexical",
) -> tuple[EmbeddingStore, list[dict[str, Any]], str]:
    chunker = make_chunker(strategy, chunk_size)
    embedder = make_embedder(provider)
    store = EmbeddingStore(
        collection_name=f"benchmark_{strategy}", embedding_fn=embedder
    )
    inventory: list[dict[str, Any]] = []

    for path in sorted(data_dir.glob("*.md")):
        metadata, content = parse_frontmatter(path)
        chunks = chunker.chunk(content)
        documents = [
            Document(
                id=f"{metadata['doc_id']}#{index}",
                content=chunk,
                metadata={
                    **metadata,
                    "doc_id": metadata["doc_id"],
                    "chunk_index": index,
                    "strategy": strategy,
                    "section_path": section_path(chunk),
                },
            )
            for index, chunk in enumerate(chunks)
        ]
        store.add_documents(documents)
        inventory.append(
            {
                "doc_id": metadata["doc_id"],
                "chunks": len(chunks),
                "avg_length": (
                    sum(len(chunk) for chunk in chunks) / len(chunks)
                    if chunks
                    else 0.0
                ),
            }
        )
    backend_name = getattr(embedder, "_backend_name", embedder.__class__.__name__)
    return store, inventory, backend_name


def is_relevant(result: dict[str, Any], benchmark_case: dict[str, Any]) -> bool:
    content = result["content"].casefold()
    return (
        result["metadata"].get("doc_id") == benchmark_case["gold_doc_id"]
        and any(marker.casefold() in content for marker in benchmark_case["markers"])
    )


def context_is_complete(
    results: list[dict[str, Any]], benchmark_case: dict[str, Any]
) -> bool:
    relevant_text = "\n".join(
        result["content"].casefold()
        for result in results
        if result["metadata"].get("doc_id") == benchmark_case["gold_doc_id"]
    )
    return all(
        marker.casefold() in relevant_text for marker in benchmark_case["markers"]
    )


def extractive_answer(query: str, results: list[dict[str, Any]]) -> str:
    query_terms = {
        token
        for token in TOKEN_PATTERN.findall(query.casefold())
        if token not in STOP_WORDS and len(token) > 1
    }
    candidates: list[tuple[float, str, str]] = []
    for result_index, result in enumerate(results):
        source = result["metadata"].get("doc_id", result.get("id", "unknown"))
        for sentence in SENTENCE_PATTERN.split(result["content"]):
            cleaned = sentence.strip()
            if len(cleaned) < 25 or cleaned.startswith("#"):
                continue
            sentence_terms = set(TOKEN_PATTERN.findall(cleaned.casefold()))
            overlap = len(query_terms & sentence_terms)
            score = (
                overlap / max(1, len(query_terms))
                + (len(results) - result_index) * 0.02
            )
            candidates.append((score, cleaned, source))

    candidates.sort(key=lambda item: (item[0], -len(item[1])), reverse=True)
    if not candidates or candidates[0][0] == 0:
        return "Không tìm thấy thông tin đủ liên quan trong ngữ cảnh truy xuất."

    selected: list[str] = []
    for _, sentence, source in candidates:
        answer_part = f"{sentence} [Nguồn: {source}]"
        if answer_part not in selected:
            selected.append(answer_part)
        if len(selected) == 3:
            break
    return " ".join(selected)


def run_benchmark(
    data_dir: Path,
    chunk_size: int,
    top_k: int,
    strategy: str = "heading",
    provider: str = "lexical",
) -> str:
    store, inventory, backend_name = build_store(
        data_dir, chunk_size, strategy=strategy, provider=provider
    )
    lines = [
        "BENCHMARK CÁ NHÂN — TRẦN THỊ THU HIỀN",
        f"Chiến lược: {strategy}",
        f"Chunk size: {chunk_size}",
        f"Embedding: {backend_name}",
        f"Tổng chunks: {store.get_collection_size()}",
        "",
        "THỐNG KÊ TÀI LIỆU",
    ]
    for item in inventory:
        lines.append(
            f"- {item['doc_id']}: {item['chunks']} chunks, "
            f"avg_length={item['avg_length']:.1f}"
        )

    relevant_count = 0
    points = 0
    lines.append("")
    lines.append("KẾT QUẢ 5 CÂU HỎI")
    for number, benchmark in enumerate(BENCHMARKS, start=1):
        benchmark_cases = benchmark.get("variants", [benchmark])
        case_ranks: list[int | None] = []
        case_completeness: list[bool] = []
        lines.extend(["", f"[{number}] {benchmark['query']}"])

        for benchmark_case in benchmark_cases:
            results = store.search_with_filter(
                benchmark["query"],
                top_k=top_k,
                metadata_filter=benchmark_case["metadata_filter"],
            )
            relevant_ranks = [
                rank
                for rank, result in enumerate(results, start=1)
                if is_relevant(result, benchmark_case)
            ]
            first_rank = relevant_ranks[0] if relevant_ranks else None
            complete = context_is_complete(results, benchmark_case)
            case_ranks.append(first_rank)
            case_completeness.append(complete)

            label = benchmark_case.get("label")
            if label:
                lines.append(f"Nhánh: {label}")
            lines.extend(
                [
                    f"Filter: {benchmark_case['metadata_filter']}",
                    f"Gold: {benchmark_case['gold_answer']}",
                ]
            )
            for rank, result in enumerate(results, start=1):
                metadata = result["metadata"]
                preview = " ".join(result["content"].split())[:260].rstrip()
                lines.append(
                    f"  Top-{rank} score={result['score']:.6f} "
                    f"doc_id={metadata.get('doc_id')} "
                    f"section={metadata.get('section_path')} "
                    f"relevant={is_relevant(result, benchmark_case)}"
                )
                lines.append(f"    {preview}")
            lines.append(f"Answer: {extractive_answer(benchmark['query'], results)}")
            lines.append(
                "Relevant rank: "
                + (str(first_rank) if first_rank else "không có trong top-3")
            )
            lines.append(f"Top-3 đủ các ý của gold answer: {complete}")

        if all(rank is not None for rank in case_ranks):
            relevant_count += 1
            if all(rank == 1 for rank in case_ranks) and all(case_completeness):
                points += 2
            else:
                points += 1

        if benchmark.get("compare_without_filter"):
            unfiltered = store.search(benchmark["query"], top_k=top_k)
            lines.append("A/B không filter:")
            for rank, result in enumerate(unfiltered, start=1):
                lines.append(
                    f"  Top-{rank} score={result['score']:.6f} "
                    f"doc_id={result['metadata'].get('doc_id')} "
                    f"audience={result['metadata'].get('audience')}"
                )

    lines.extend(
        [
            "",
            "TỔNG KẾT",
            f"Top-3 chứa chunk liên quan: {relevant_count}/5",
            f"Điểm retrieval theo vị trí: {points}/10",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Hiền's HeadingChunker benchmark.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/chinh-sach-shopee"),
    )
    parser.add_argument("--chunk-size", type=int, default=700)
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument(
        "--strategy",
        choices=("fixed", "recursive", "heading", "clause"),
        default="heading",
    )
    parser.add_argument(
        "--provider",
        choices=("lexical", "mock", "local", "openai", "gemini"),
        default="lexical",
        help="Embedding backend. API providers read credentials from .env.",
    )
    parser.add_argument(
        "--all-strategies",
        action="store_true",
        help="Run the four group strategies with their agreed chunk sizes.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("ket_qua_benchmark.txt"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.data_dir.is_dir():
        raise SystemExit(f"Data directory not found: {args.data_dir}")
    if args.all_strategies:
        configurations = (
            ("fixed", 500),
            ("recursive", 400),
            ("heading", 800),
            ("clause", 400),
        )
        outputs = [
            run_benchmark(
                args.data_dir,
                chunk_size,
                max(1, args.top_k),
                strategy=strategy,
                provider=args.provider,
            )
            for strategy, chunk_size in configurations
        ]
        output = "\n".join(outputs)
    else:
        output = run_benchmark(
            args.data_dir,
            max(1, args.chunk_size),
            max(1, args.top_k),
            strategy=args.strategy,
            provider=args.provider,
        )
    args.output.write_text(output, encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(output)
    print(f"Đã lưu: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
