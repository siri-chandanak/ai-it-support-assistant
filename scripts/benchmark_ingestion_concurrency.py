from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from time import perf_counter

from scripts.benchmark_ingestion import (
    TEST_FILES,
    benchmark_file,
)


def main() -> None:
    files = [path for path in TEST_FILES if path.exists()][:2]

    if len(files) < 2:
        raise RuntimeError("Need at least two performance test files.")

    started = perf_counter()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                benchmark_file,
                file_path,
            )
            for file_path in files
        ]

        for future in as_completed(futures):
            print(future.result())

    elapsed = perf_counter() - started

    print(f"Concurrent ingestion total: {elapsed:.2f}s")


if __name__ == "__main__":
    main()
