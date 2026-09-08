import pytest

from ai_it_support_assistant.services.chunking_service import (
    ChunkingError,
    chunk_text,
)


def test_short_text_creates_single_chunk() -> None:
    chunks = chunk_text(
        document_id="doc-123",
        text="Restart the VPN client.",
        chunk_size=100,
        chunk_overlap=20,
        allowed_roles=["reader"],
    )

    assert len(chunks) == 1
    assert chunks[0].chunk_id == "doc-123:0"
    assert chunks[0].document_id == "doc-123"
    assert chunks[0].chunk_index == 0
    assert chunks[0].text == "Restart the VPN client."


def test_long_text_creates_overlapping_chunks() -> None:
    text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    chunks = chunk_text(
        document_id="doc-456",
        text=text,
        chunk_size=10,
        chunk_overlap=2,
        allowed_roles=["reader"],
    )

    assert len(chunks) == 3

    assert chunks[0].text == "ABCDEFGHIJ"
    assert chunks[1].text == "IJKLMNOPQR"
    assert chunks[2].text == "QRSTUVWXYZ"


def test_reject_overlap_equal_to_chunk_size() -> None:
    with pytest.raises(
        ChunkingError,
        match="chunk_overlap must be smaller than chunk_size",
    ):
        chunk_text(
            document_id="doc-123",
            text="VPN troubleshooting guide",
            chunk_size=100,
            chunk_overlap=100,
            allowed_roles=["reader"],
        )


def test_reject_negative_overlap() -> None:
    with pytest.raises(
        ChunkingError,
        match="chunk_overlap cannot be negative",
    ):
        chunk_text(
            document_id="doc-123",
            text="VPN troubleshooting guide",
            chunk_size=100,
            chunk_overlap=-1,
            allowed_roles=["reader"],
        )
