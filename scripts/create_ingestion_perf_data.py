from pathlib import Path

TARGET = Path("performance/data/ingestion")


def write_file(
    *,
    name: str,
    target_bytes: int,
) -> None:
    TARGET.mkdir(
        parents=True,
        exist_ok=True,
    )

    paragraph = (
        "VPN troubleshooting documentation. "
        "Users should verify credentials, "
        "network connectivity, MFA status, "
        "client configuration, and service "
        "availability before escalation.\n"
    )

    output = ""

    while len(output.encode("utf-8")) < target_bytes:
        output += paragraph

    Path(TARGET / name).write_text(
        output,
        encoding="utf-8",
    )


def main() -> None:
    write_file(
        name="small.txt",
        target_bytes=10 * 1024,
    )

    write_file(
        name="medium.txt",
        target_bytes=1 * 1024 * 1024,
    )

    write_file(
        name="large.txt",
        target_bytes=4_800 * 1024,
    )


if __name__ == "__main__":
    main()
