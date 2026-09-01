from pathlib import Path

import pytest

from ai_it_support_assistant.services.text_extraction_service import (
    TextExtractionError,
    extract_text,
)


def test_extract_text_from_txt_file(tmp_path: Path) -> None:
    document = tmp_path / "runbook.txt"
    document.write_text(
        "Restart the VPN client before escalating.",
        encoding="utf-8",
    )

    text = extract_text(document)

    assert text == "Restart the VPN client before escalating."


def test_extract_text_strips_outer_whitespace(tmp_path: Path) -> None:
    document = tmp_path / "notes.md"
    document.write_text(
        "\n\n# VPN Guide\n\nRestart the client.\n\n",
        encoding="utf-8",
    )

    text = extract_text(document)

    assert text == "# VPN Guide\n\nRestart the client."


def test_reject_document_with_no_usable_text(tmp_path: Path) -> None:
    document = tmp_path / "empty.txt"
    document.write_text("   \n\n   ", encoding="utf-8")

    with pytest.raises(
        TextExtractionError,
        match="Document contains no usable text",
    ):
        extract_text(document)
