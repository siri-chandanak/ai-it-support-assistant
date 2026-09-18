from typing import Any

SENSITIVE_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "password",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "client_secret",
    "kubeconfig",
    "jwt",
    "prompt",
    "document_text",
    "chunk_text",
    "embedding",
}


REDACTED = "[REDACTED]"


def is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower()

    return any(sensitive_key in normalized for sensitive_key in SENSITIVE_KEYS)


def redact_mapping(
    values: dict[str, Any],
) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}

    for key, value in values.items():
        if is_sensitive_key(key):
            sanitized[key] = REDACTED
        else:
            sanitized[key] = value

    return sanitized
