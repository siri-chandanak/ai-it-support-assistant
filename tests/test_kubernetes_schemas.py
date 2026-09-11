import pytest
from pydantic import ValidationError

from ai_it_support_assistant.schemas.kubernetes import (
    DeploymentRestartActionPayload,
    DeploymentRestartRequest,
)


def test_deployment_restart_request_valid():
    request = DeploymentRestartRequest(
        name="payment-api",
        namespace="dev",
    )

    assert request.name == "payment-api"
    assert request.namespace == "dev"


def test_deployment_restart_rejects_invalid_name():
    with pytest.raises(ValidationError):
        DeploymentRestartRequest(
            name="Payment_API",
            namespace="dev",
        )


def test_deployment_restart_rejects_invalid_namespace():
    with pytest.raises(ValidationError):
        DeploymentRestartRequest(
            name="payment-api",
            namespace="DEV_NAMESPACE",
        )


def test_restart_payload_valid():
    payload = DeploymentRestartActionPayload(
        name="payment-api",
        namespace="dev",
        evidence_desired_replicas=3,
        evidence_ready_replicas=2,
        evidence_available_replicas=2,
    )

    assert payload.name == "payment-api"
    assert payload.namespace == "dev"
    assert payload.evidence_desired_replicas == 3
    assert payload.warnings == []


def test_restart_payload_supports_warning():
    payload = DeploymentRestartActionPayload(
        name="vpn-api",
        namespace="dev",
        evidence_desired_replicas=1,
        evidence_ready_replicas=1,
        evidence_available_replicas=1,
        warnings=[
            ("Deployment has one desired replica; restart may cause temporary unavailability.")
        ],
    )

    assert len(payload.warnings) == 1


def test_restart_payload_rejects_negative_replicas():
    with pytest.raises(ValidationError):
        DeploymentRestartActionPayload(
            name="payment-api",
            namespace="dev",
            evidence_desired_replicas=-1,
            evidence_ready_replicas=0,
            evidence_available_replicas=0,
        )


def test_restart_request_forbids_extra_fields():
    with pytest.raises(ValidationError):
        DeploymentRestartRequest(
            name="payment-api",
            namespace="dev",
            command="rm -rf /",
        )
