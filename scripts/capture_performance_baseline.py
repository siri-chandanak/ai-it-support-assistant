import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from ai_it_support_assistant.core.config import (
    get_settings,
)

RESULTS_DIR = Path("performance/results")

OUTPUT_FILE = RESULTS_DIR / "performance-environment.json"

EMBEDDING_RESULT_FILE = RESULTS_DIR / "embedding-benchmark.json"

QDRANT_RESULT_FILE = RESULTS_DIR / "qdrant-benchmark.json"


def get_git_sha() -> str:
    try:
        result = subprocess.run(
            [
                "git",
                "rev-parse",
                "HEAD",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        return result.stdout.strip()

    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
    ):
        return "unknown"


def read_json_if_exists(
    path: Path,
) -> dict | None:
    if not path.exists():
        return None

    return json.loads(path.read_text(encoding="utf-8"))


def env_int(
    name: str,
) -> int | None:
    value = os.getenv(name)

    if value is None:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def main() -> None:
    settings = get_settings()

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    embedding_results = read_json_if_exists(EMBEDDING_RESULT_FILE)

    qdrant_results = read_json_if_exists(QDRANT_RESULT_FILE)

    baseline = {
        "generated_at_utc": (datetime.now(UTC).isoformat()),
        "git_sha": get_git_sha(),
        "environment": (settings.environment),
        "application": {
            "api_replicas": (env_int("PERF_API_REPLICAS")),
            "worker_replicas": (env_int("PERF_WORKER_REPLICAS")),
        },
        "models": {
            "embedding_model": (settings.embedding_model_name),
            "llm_model": (settings.llm_model),
        },
        "rag": {
            "top_k": (settings.rag_top_k),
            "score_threshold": (settings.rag_score_threshold),
            "embedding_cache_enabled": (
                getattr(
                    settings,
                    "embedding_cache_enabled",
                    None,
                )
            ),
            "retrieval_cache_enabled": (
                getattr(
                    settings,
                    "retrieval_cache_enabled",
                    None,
                )
            ),
        },
        "qdrant": {
            "url": settings.qdrant_url,
            "collection": (settings.qdrant_collection_name),
            "timeout_seconds": (settings.qdrant_timeout_seconds),
        },
        "authorization": {
            "pdp_mode": os.getenv("PERF_PDP_MODE"),
            "policy_revision": os.getenv("PERF_POLICY_REVISION"),
        },
        "embedding_benchmark": (embedding_results),
        "qdrant_benchmark": (qdrant_results),
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            baseline,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("Performance environment captured")
    print("--------------------------------")
    print(f"Git SHA:     {baseline['git_sha']}")
    print(f"Environment: {baseline['environment']}")
    print(f"Embedding:   {settings.embedding_model_name}")
    print(f"LLM:         {settings.llm_model}")
    print(f"RAG top_k:   {settings.rag_top_k}")
    print(f"Collection:  {settings.qdrant_collection_name}")
    print()
    print(f"Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
