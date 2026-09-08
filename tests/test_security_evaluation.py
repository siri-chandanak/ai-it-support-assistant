from ai_it_support_assistant.cache.cache_service import (
    build_retrieval_cache_key,
)
from ai_it_support_assistant.evaluation.security_evaluator import (
    contains_expected_allowed_document,
    contains_forbidden_citations,
    contains_forbidden_documents,
    contains_forbidden_text,
)
from ai_it_support_assistant.schemas.rag import (
    RAGSource,
)
from ai_it_support_assistant.schemas.retrieval import (
    RetrievedChunk,
)


def test_forbidden_text_is_detected() -> None:
    assert contains_forbidden_text(
        answer=("Use RESTRICTED_IT_CANARY_8F92A1 for this process."),
        forbidden_fragments=[
            "RESTRICTED_IT_CANARY_8F92A1",
        ],
    )


def test_safe_answer_has_no_forbidden_text() -> None:
    assert not contains_forbidden_text(
        answer=("The available documentation does not provide that information."),
        forbidden_fragments=[
            "RESTRICTED_IT_CANARY_8F92A1",
        ],
    )


def test_forbidden_retrieved_document_is_detected() -> None:
    chunks = [
        RetrievedChunk(
            chunk_id="secret:0",
            document_id="secret-doc",
            chunk_index=0,
            text="fake restricted content",
            score=0.9,
        )
    ]

    assert contains_forbidden_documents(
        chunks=chunks,
        forbidden_document_ids=[
            "secret-doc",
        ],
    )


def test_allowed_document_is_not_a_leak() -> None:
    chunks = [
        RetrievedChunk(
            chunk_id="general:0",
            document_id="general-doc",
            chunk_index=0,
            text="general help",
            score=0.9,
        )
    ]

    assert not contains_forbidden_documents(
        chunks=chunks,
        forbidden_document_ids=[
            "secret-doc",
        ],
    )


def test_forbidden_citation_is_detected() -> None:
    sources = [
        RAGSource(
            chunk_id="secret:0",
            document_id="secret-doc",
            chunk_index=0,
            score=0.93,
        )
    ]

    assert contains_forbidden_citations(
        sources=sources,
        forbidden_document_ids=[
            "secret-doc",
        ],
    )


def test_expected_document_is_detected() -> None:
    chunks = [
        RetrievedChunk(
            chunk_id="vpn:0",
            document_id="vpn-doc",
            chunk_index=0,
            text="VPN troubleshooting",
            score=0.9,
        )
    ]

    assert contains_expected_allowed_document(
        chunks=chunks,
        expected_document_ids=[
            "vpn-doc",
        ],
    )


def test_missing_expected_document_fails() -> None:
    chunks = [
        RetrievedChunk(
            chunk_id="general:0",
            document_id="general-doc",
            chunk_index=0,
            text="General support",
            score=0.9,
        )
    ]

    assert not contains_expected_allowed_document(
        chunks=chunks,
        expected_document_ids=[
            "vpn-doc",
        ],
    )


def test_same_query_different_roles_have_different_retrieval_cache_keys() -> None:
    admin_key = build_retrieval_cache_key(
        query=("How do I recover production VPN?"),
        model_name="model-a",
        collection_name="docs",
        top_k=3,
        user_roles=["admin"],
    )

    reader_key = build_retrieval_cache_key(
        query=("How do I recover production VPN?"),
        model_name="model-a",
        collection_name="docs",
        top_k=3,
        user_roles=["reader"],
    )

    assert admin_key != reader_key


def test_role_order_does_not_change_cache_key() -> None:
    key_one = build_retrieval_cache_key(
        query="VPN",
        model_name="model",
        collection_name="docs",
        top_k=3,
        user_roles=[
            "admin",
            "it_support",
        ],
    )

    key_two = build_retrieval_cache_key(
        query="VPN",
        model_name="model",
        collection_name="docs",
        top_k=3,
        user_roles=[
            "it_support",
            "admin",
        ],
    )

    assert key_one == key_two
