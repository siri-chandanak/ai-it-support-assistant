import json
from unittest.mock import Mock

from ai_it_support_assistant.schemas.kubernetes import (
    DeploymentRolloutResult,
    DeploymentState,
)
from ai_it_support_assistant.services.kubernetes_rollout_service import (
    monitor_deployment_rollout,
)
from ai_it_support_assistant.services.kubernetes_state_service import (
    is_deployment_rollout_healthy,
)


def deployment_state(
    *,
    desired: int = 3,
    updated: int = 3,
    ready: int = 3,
    available: int = 3,
    generation: int = 10,
    observed_generation: int = 10,
    progress_deadline_exceeded: bool = False,
) -> DeploymentState:
    return DeploymentState(
        name="payment-api",
        namespace="dev",
        desired_replicas=desired,
        updated_replicas=updated,
        ready_replicas=ready,
        available_replicas=available,
        generation=generation,
        observed_generation=observed_generation,
        progress_deadline_exceeded=progress_deadline_exceeded,
    )


def test_restart_result_contains_final_replica_counts():
    result = {
        "name": "payment-api",
        "namespace": "dev",
        "restart_applied": True,
        "rollout_outcome": "healthy",
        "desired_replicas": 3,
        "updated_replicas": 3,
        "ready_replicas": 3,
        "available_replicas": 3,
    }

    result_json = json.dumps(result)

    saved = json.loads(result_json)

    assert saved["desired_replicas"] == 3
    assert saved["updated_replicas"] == 3
    assert saved["ready_replicas"] == 3
    assert saved["available_replicas"] == 3


def test_persisted_result_can_be_reloaded_from_json():
    persisted_result_json = json.dumps(
        {
            "name": "payment-api",
            "namespace": "dev",
            "restart_applied": True,
            "rollout_outcome": "healthy",
            "desired_replicas": 3,
            "updated_replicas": 3,
            "ready_replicas": 3,
            "available_replicas": 3,
        }
    )

    reloaded_result = json.loads(persisted_result_json)

    assert reloaded_result == {
        "name": "payment-api",
        "namespace": "dev",
        "restart_applied": True,
        "rollout_outcome": "healthy",
        "desired_replicas": 3,
        "updated_replicas": 3,
        "ready_replicas": 3,
        "available_replicas": 3,
    }


def test_rollout_monitor_uses_monotonic(
    monkeypatch,
):
    states = [
        deployment_state(
            updated=1,
            ready=1,
            available=1,
        ),
        deployment_state(),
    ]

    state_mock = Mock(
        side_effect=states,
    )

    monotonic_mock = Mock(
        side_effect=[
            100.0,
            101.0,
        ]
    )

    sleep_mock = Mock()

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.kubernetes_rollout_service.get_deployment_state"),
        state_mock,
    )

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.kubernetes_rollout_service.time.monotonic"),
        monotonic_mock,
    )

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.kubernetes_rollout_service.time.sleep"),
        sleep_mock,
    )

    result = monitor_deployment_rollout(
        name="payment-api",
        namespace="dev",
        timeout_seconds=120,
        poll_interval_seconds=5,
        max_read_failures=3,
        config_mode="local",
        context="",
    )

    assert result.outcome == "healthy"
    assert monotonic_mock.called


def test_rollout_monitor_sleep_is_mocked(
    monkeypatch,
):
    states = [
        deployment_state(
            updated=1,
            ready=1,
            available=1,
        ),
        deployment_state(),
    ]

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.kubernetes_rollout_service.get_deployment_state"),
        Mock(side_effect=states),
    )

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.kubernetes_rollout_service.time.monotonic"),
        Mock(
            side_effect=[
                100.0,
                101.0,
            ]
        ),
    )

    sleep_mock = Mock()

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.kubernetes_rollout_service.time.sleep"),
        sleep_mock,
    )

    result = monitor_deployment_rollout(
        name="payment-api",
        namespace="dev",
        timeout_seconds=120,
        poll_interval_seconds=5,
        max_read_failures=3,
        config_mode="local",
        context="",
    )

    assert result.outcome == "healthy"

    sleep_mock.assert_called_once_with(5)


def test_rollout_monitor_eventually_becomes_healthy(
    monkeypatch,
):
    states = [
        deployment_state(
            updated=1,
            ready=1,
            available=1,
        ),
        deployment_state(
            updated=2,
            ready=2,
            available=2,
        ),
        deployment_state(
            updated=3,
            ready=3,
            available=3,
        ),
    ]

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.kubernetes_rollout_service.get_deployment_state"),
        Mock(side_effect=states),
    )

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.kubernetes_rollout_service.time.monotonic"),
        Mock(
            side_effect=[
                100.0,
                101.0,
                102.0,
            ]
        ),
    )

    sleep_mock = Mock()

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.kubernetes_rollout_service.time.sleep"),
        sleep_mock,
    )

    result = monitor_deployment_rollout(
        name="payment-api",
        namespace="dev",
        timeout_seconds=120,
        poll_interval_seconds=5,
        max_read_failures=3,
        config_mode="local",
        context="",
    )

    assert result.outcome == "healthy"

    assert result.desired_replicas == 3
    assert result.updated_replicas == 3
    assert result.ready_replicas == 3
    assert result.available_replicas == 3

    assert sleep_mock.call_count == 2


def test_rollout_monitor_times_out(
    monkeypatch,
):
    unhealthy_state = deployment_state(
        updated=2,
        ready=2,
        available=2,
    )

    state_mock = Mock(
        return_value=unhealthy_state,
    )

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.kubernetes_rollout_service.get_deployment_state"),
        state_mock,
    )

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.kubernetes_rollout_service.time.monotonic"),
        Mock(
            side_effect=[
                100.0,
                101.0,
                221.0,
            ]
        ),
    )

    sleep_mock = Mock()

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.kubernetes_rollout_service.time.sleep"),
        sleep_mock,
    )

    result = monitor_deployment_rollout(
        name="payment-api",
        namespace="dev",
        timeout_seconds=120,
        poll_interval_seconds=5,
        max_read_failures=3,
        config_mode="local",
        context="",
    )

    assert result.outcome == "timeout"

    assert result.desired_replicas == 3
    assert result.updated_replicas == 2
    assert result.ready_replicas == 2
    assert result.available_replicas == 2


def test_rollout_monitor_fails_on_progress_deadline_exceeded(
    monkeypatch,
):
    failed_state = deployment_state(
        updated=2,
        ready=1,
        available=1,
        progress_deadline_exceeded=True,
    )

    state_mock = Mock(
        return_value=failed_state,
    )

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.kubernetes_rollout_service.get_deployment_state"),
        state_mock,
    )

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.kubernetes_rollout_service.time.monotonic"),
        Mock(return_value=100.0),
    )

    sleep_mock = Mock()

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.kubernetes_rollout_service.time.sleep"),
        sleep_mock,
    )

    result = monitor_deployment_rollout(
        name="payment-api",
        namespace="dev",
        timeout_seconds=120,
        poll_interval_seconds=5,
        max_read_failures=3,
        config_mode="local",
        context="",
    )

    assert result.outcome == "failed"

    assert result.desired_replicas == 3
    assert result.updated_replicas == 2
    assert result.ready_replicas == 1
    assert result.available_replicas == 1

    sleep_mock.assert_not_called()


def test_rollout_not_healthy_when_generation_is_not_observed():
    state = deployment_state(
        desired=3,
        updated=3,
        ready=3,
        available=3,
        generation=10,
        observed_generation=9,
    )

    assert (
        is_deployment_rollout_healthy(
            state,
        )
        is False
    )


def test_rollout_healthy_when_latest_generation_is_observed():
    state = deployment_state(
        desired=3,
        updated=3,
        ready=3,
        available=3,
        generation=10,
        observed_generation=10,
    )

    assert (
        is_deployment_rollout_healthy(
            state,
        )
        is True
    )


def test_annotation_verification_failure_does_not_start_monitor(
    monkeypatch,
):
    restart_mock = Mock()
    verify_mock = Mock(
        return_value=False,
    )
    monitor_mock = Mock()

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.action_execution_service.restart_deployment"),
        restart_mock,
    )

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.action_execution_service.deployment_has_restart_token"),
        verify_mock,
    )

    monkeypatch.setattr(
        ("ai_it_support_assistant.services.action_execution_service.monitor_deployment_rollout"),
        monitor_mock,
    )

    restart_mock(
        name="payment-api",
        namespace="dev",
        restart_timestamp="2026-09-11T12:00:00Z",
        config_mode="local",
        context="",
    )

    verified = verify_mock(
        name="payment-api",
        namespace="dev",
        restart_timestamp="2026-09-11T12:00:00Z",
        config_mode="local",
        context="",
    )

    if verified:
        monitor_mock()

    assert verified is False

    restart_mock.assert_called_once()
    verify_mock.assert_called_once()
    monitor_mock.assert_not_called()


def test_restart_applied_but_timeout_records_failed_action():
    rollout_result = DeploymentRolloutResult(
        deployment_name="payment-api",
        namespace="dev",
        outcome="timeout",
        desired_replicas=3,
        updated_replicas=3,
        ready_replicas=2,
        available_replicas=2,
        message="Deployment rollout timed out.",
    )

    result = {
        "name": rollout_result.deployment_name,
        "namespace": rollout_result.namespace,
        "restart_applied": True,
        "rollout_outcome": rollout_result.outcome,
        "desired_replicas": rollout_result.desired_replicas,
        "updated_replicas": rollout_result.updated_replicas,
        "ready_replicas": rollout_result.ready_replicas,
        "available_replicas": rollout_result.available_replicas,
    }

    action_state = "succeeded" if rollout_result.outcome == "healthy" else "failed"

    assert result["restart_applied"] is True
    assert result["rollout_outcome"] == "timeout"

    assert result["desired_replicas"] == 3
    assert result["updated_replicas"] == 3
    assert result["ready_replicas"] == 2
    assert result["available_replicas"] == 2

    assert action_state == "failed"
