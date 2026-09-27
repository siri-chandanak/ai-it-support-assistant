from __future__ import annotations

import json
import os
import time
from pathlib import Path

import psutil

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.services.chunking_service import (
    chunk_text,
)
from ai_it_support_assistant.services.embedding_service import (
    embed_chunks,
)
from ai_it_support_assistant.services.text_extraction_service import (
    extract_text,
)
from ai_it_support_assistant.services.vector_store_service import (
    store_chunk_vectors,
)

TEST_FILES = [
    Path("performance/data/ingestion/small.txt"),
    Path("performance/data/ingestion/medium.txt"),
    Path("performance/data/ingestion/large.txt"),
]

RESULTS_PATH = Path("performance/results/ingestion-benchmark.json")


def current_memory_mb() -> float:
    process = psutil.Process(os.getpid())

    memory_bytes = process.memory_info().rss

    return memory_bytes / (1024 * 1024)


def benchmark_file(
    file_path: Path,
) -> dict[str, object]:
    settings = get_settings()

    total_started = time.perf_counter()
    memory_before = current_memory_mb()

    extraction_started = time.perf_counter()

    text = extract_text(
        file_path=file_path,
    )

    extraction_ms = (time.perf_counter() - extraction_started) * 1000

    chunk_started = time.perf_counter()

    chunks = chunk_text(
        document_id=file_path.stem,
        text=text,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        allowed_roles=["reader"],
    )

    chunk_ms = (time.perf_counter() - chunk_started) * 1000

    embedding_started = time.perf_counter()

    embeddings = embed_chunks(
        chunks=chunks,
        model_name=settings.embedding_model_name,
    )

    embedding_ms = (time.perf_counter() - embedding_started) * 1000

    qdrant_started = time.perf_counter()

    stored = store_chunk_vectors(
        chunks=chunks,
        embeddings=embeddings,
        qdrant_url=settings.qdrant_url,
        collection_name=(settings.qdrant_collection_name),
        qdrant_timeout_seconds=(settings.qdrant_timeout_seconds),
    )

    qdrant_ms = (time.perf_counter() - qdrant_started) * 1000

    total_ms = (time.perf_counter() - total_started) * 1000

    memory_after = current_memory_mb()

    return {
        "file": str(file_path),
        "size_bytes": file_path.stat().st_size,
        "chunk_count": len(chunks),
        "stored_vectors": stored,
        "extraction_ms": round(
            extraction_ms,
            2,
        ),
        "chunking_ms": round(
            chunk_ms,
            2,
        ),
        "embedding_ms": round(
            embedding_ms,
            2,
        ),
        "qdrant_upsert_ms": round(
            qdrant_ms,
            2,
        ),
        "total_ms": round(
            total_ms,
            2,
        ),
        "memory_before_mb": round(
            memory_before,
            2,
        ),
        "memory_after_mb": round(
            memory_after,
            2,
        ),
    }


def main() -> None:
    RESULTS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    results: list[dict[str, object]] = []

    for file_path in TEST_FILES:
        if not file_path.exists():
            print(f"Skipping missing test file: {file_path}")
            continue

        result = benchmark_file(file_path)

        print(result)

        results.append(result)

    RESULTS_PATH.write_text(
        json.dumps(
            results,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
