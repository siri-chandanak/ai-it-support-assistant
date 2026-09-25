from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient, models

from ai_it_support_assistant.core.config import get_settings
from ai_it_support_assistant.schemas.auth import User
from ai_it_support_assistant.services.embedding_service import embed_query
from ai_it_support_assistant.services.retrieval_service import retrieve_chunks

pytestmark = pytest.mark.e2e


def test_reader_cannot_retrieve_admin_only_evidence() -> None:
    settings = get_settings()

    unique_id = uuid4()

    document_id = f"e2e-admin-{unique_id}"
    chunk_id = f"{document_id}:0"

    restricted_marker = f"E2E-ADMIN-SECRET-{unique_id}"

    question = f"What is the internal recovery phrase {restricted_marker}?"

    restricted_text = (
        f"The internal recovery phrase is {restricted_marker}. "
        "This information is restricted to administrators."
    )

    vector = embed_query(
        query=question,
        model_name=settings.embedding_model_name,
        cache_enabled=False,
    )

    client = QdrantClient(
        url=settings.qdrant_url,
        timeout=settings.qdrant_timeout_seconds,
    )

    point_id = str(uuid4())

    try:
        client.upsert(
            collection_name=settings.qdrant_collection_name,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "chunk_id": chunk_id,
                        "document_id": document_id,
                        "chunk_index": 0,
                        "text": restricted_text,
                        "allowed_roles": ["admin"],
                    },
                )
            ],
            wait=True,
        )

        admin_results = retrieve_chunks(
            query=question,
            top_k=3,
            embedding_model_name=settings.embedding_model_name,
            embedding_cache_enabled=False,
            retrieval_cache_enabled=False,
            qdrant_url=settings.qdrant_url,
            collection_name=settings.qdrant_collection_name,
            qdrant_timeout_seconds=settings.qdrant_timeout_seconds,
            qdrant_max_retries=settings.qdrant_max_attempts,
            user_roles=["admin"],
        )

        reader_results = retrieve_chunks(
            query=question,
            top_k=3,
            embedding_model_name=settings.embedding_model_name,
            embedding_cache_enabled=False,
            retrieval_cache_enabled=False,
            qdrant_url=settings.qdrant_url,
            collection_name=settings.qdrant_collection_name,
            qdrant_timeout_seconds=settings.qdrant_timeout_seconds,
            qdrant_max_retries=settings.qdrant_max_attempts,
            user_roles=["reader"],
        )

        assert any(chunk.document_id == document_id for chunk in admin_results)

        assert all(chunk.document_id != document_id for chunk in reader_results)

        assert all(restricted_marker not in chunk.text for chunk in reader_results)

    finally:
        client.delete(
            collection_name=settings.qdrant_collection_name,
            points_selector=models.PointIdsList(
                points=[point_id],
            ),
            wait=True,
        )


def test_retrieval_cache_does_not_leak_admin_evidence_to_reader() -> None:
    settings = get_settings()

    unique_id = uuid4()

    document_id = f"e2e-cache-admin-{unique_id}"
    chunk_id = f"{document_id}:0"

    restricted_marker = f"E2E-CACHE-SECRET-{unique_id}"

    question = f"What is the restricted cache phrase {restricted_marker}?"

    restricted_text = f"The restricted cache phrase is {restricted_marker}. Administrators only."

    vector = embed_query(
        query=question,
        model_name=settings.embedding_model_name,
        cache_enabled=False,
    )

    client = QdrantClient(
        url=settings.qdrant_url,
        timeout=settings.qdrant_timeout_seconds,
    )

    point_id = str(uuid4())

    try:
        client.upsert(
            collection_name=settings.qdrant_collection_name,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "chunk_id": chunk_id,
                        "document_id": document_id,
                        "chunk_index": 0,
                        "text": restricted_text,
                        "allowed_roles": ["admin"],
                    },
                )
            ],
            wait=True,
        )

        admin_results = retrieve_chunks(
            query=question,
            top_k=3,
            embedding_model_name=settings.embedding_model_name,
            embedding_cache_enabled=False,
            retrieval_cache_enabled=True,
            qdrant_url=settings.qdrant_url,
            collection_name=settings.qdrant_collection_name,
            qdrant_timeout_seconds=settings.qdrant_timeout_seconds,
            qdrant_max_retries=settings.qdrant_max_attempts,
            user_roles=["admin"],
        )

        assert any(chunk.document_id == document_id for chunk in admin_results)

        reader_results = retrieve_chunks(
            query=question,
            top_k=3,
            embedding_model_name=settings.embedding_model_name,
            embedding_cache_enabled=False,
            retrieval_cache_enabled=True,
            qdrant_url=settings.qdrant_url,
            collection_name=settings.qdrant_collection_name,
            qdrant_timeout_seconds=settings.qdrant_timeout_seconds,
            qdrant_max_retries=settings.qdrant_max_attempts,
            user_roles=["reader"],
        )

        assert all(chunk.document_id != document_id for chunk in reader_results)

        assert all(restricted_marker not in chunk.text for chunk in reader_results)

    finally:
        client.delete(
            collection_name=settings.qdrant_collection_name,
            points_selector=models.PointIdsList(
                points=[point_id],
            ),
            wait=True,
        )


def test_reader_final_agent_response_does_not_leak_admin_evidence(
    client: TestClient,
    reader_auth_override: User,
) -> None:
    settings = get_settings()

    unique_id = uuid4()

    document_id = f"e2e-http-admin-{unique_id}"
    chunk_id = f"{document_id}:0"

    restricted_marker = f"E2E-HTTP-ADMIN-SECRET-{unique_id}"

    question = f"What is the internal administrator phrase {restricted_marker}?"

    restricted_text = (
        f"The internal administrator phrase is "
        f"{restricted_marker}. "
        "This information is restricted to administrators."
    )

    vector = embed_query(
        query=question,
        model_name=settings.embedding_model_name,
        cache_enabled=False,
    )

    qdrant_client = QdrantClient(
        url=settings.qdrant_url,
        timeout=settings.qdrant_timeout_seconds,
    )

    point_id = str(uuid4())

    try:
        qdrant_client.upsert(
            collection_name=settings.qdrant_collection_name,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "chunk_id": chunk_id,
                        "document_id": document_id,
                        "chunk_index": 0,
                        "text": restricted_text,
                        "allowed_roles": ["admin"],
                    },
                )
            ],
            wait=True,
        )

        response = client.post(
            "/api/v1/agent/ask",
            json={
                "question": question,
            },
        )

        assert response.status_code == 200

        body = response.json()

        assert body["action"] == "rag"
        assert restricted_marker not in body["answer"]

    finally:
        qdrant_client.delete(
            collection_name=settings.qdrant_collection_name,
            points_selector=models.PointIdsList(
                points=[point_id],
            ),
            wait=True,
        )
