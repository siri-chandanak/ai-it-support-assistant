from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.main import app
from ai_it_support_assistant.services.retrieval_service import build_retrieval_cache_key

client = TestClient(app)


def test_upload_text_document(
    tmp_path: Path,
    admin_auth_override: None,
) -> None:
    settings = get_settings()

    original_storage_path = settings.document_storage_path
    settings.document_storage_path = str(tmp_path)

    try:
        with (
            patch(
                "ai_it_support_assistant.services.ingestion_service.embed_chunks",
                return_value=[[0.1, 0.2, 0.3]],
            ),
            patch(
                "ai_it_support_assistant.services.ingestion_service.store_chunk_vectors",
                return_value=1,
            ),
        ):
            response = client.post(
                "/api/v1/documents",
                files={
                    "file": (
                        "runbook.txt",
                        b"Restart the VPN client before escalating.",
                        "text/plain",
                    )
                },
                data={"allowed_roles_raw": ("reader,it_support,admin")},
            )
    finally:
        settings.document_storage_path = original_storage_path

    assert response.status_code == 201

    body = response.json()

    assert body["filename"] == "runbook.txt"
    assert body["content_type"] == "text/plain"
    assert body["chunk_count"] == 1
    assert body["indexed_chunk_count"] == 1
    assert body["status"] == "indexed"


def test_reject_unsupported_document_type(
    tmp_path: Path,
    admin_auth_override: None,
) -> None:
    settings = get_settings()
    original_storage_path = settings.document_storage_path

    settings.document_storage_path = str(tmp_path)

    try:
        response = client.post(
            "/api/v1/documents",
            files={
                "file": (
                    "payload.exe",
                    b"not really an executable",
                    "application/octet-stream",
                )
            },
        )
    finally:
        settings.document_storage_path = original_storage_path
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_reject_document_with_no_usable_text(tmp_path: Path, admin_auth_override: None) -> None:
    settings = get_settings()
    original_storage_path = settings.document_storage_path

    settings.document_storage_path = str(tmp_path)

    try:
        response = client.post(
            "/api/v1/documents",
            files={
                "file": (
                    "empty.txt",
                    b"   \n\n   ",
                    "text/plain",
                )
            },
        )
    finally:
        settings.document_storage_path = original_storage_path

    assert response.status_code == 422
    assert "no usable text" in response.json()["detail"]

    assert list(tmp_path.iterdir()) == []


def test_retrieval_cache_key_is_role_specific() -> None:
    admin_key = build_retrieval_cache_key(
        query="VPN",
        model_name="embedding-model",
        collection_name="document_chunks",
        top_k=3,
        user_roles=["admin"],
    )

    reader_key = build_retrieval_cache_key(
        query="VPN",
        model_name="embedding-model",
        collection_name="document_chunks",
        top_k=3,
        user_roles=["reader"],
    )

    assert admin_key != reader_key
