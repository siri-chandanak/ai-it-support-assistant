import pytest

from ai_it_support_assistant.services.action_state_service import (
    InvalidActionTransitionError,
    validate_action_transition,
)


def test_pending_can_be_approved() -> None:
    validate_action_transition(
        current_state="pending",
        target_state="approved",
    )


def test_pending_can_be_rejected() -> None:
    validate_action_transition(
        current_state="pending",
        target_state="rejected",
    )


def test_approved_can_be_executing() -> None:
    validate_action_transition(
        current_state="approved",
        target_state="executing",
    )


def test_executing_can_succeed() -> None:
    validate_action_transition(
        current_state="executing",
        target_state="succeeded",
    )


def test_executing_can_fail() -> None:
    validate_action_transition(
        current_state="executing",
        target_state="failed",
    )


def test_pending_cannot_go_directly_to_succeeded() -> None:
    with pytest.raises(InvalidActionTransitionError):
        validate_action_transition(
            current_state="pending",
            target_state="succeeded",
        )


def test_pending_cannot_go_directly_to_failed() -> None:
    with pytest.raises(InvalidActionTransitionError):
        validate_action_transition(
            current_state="pending",
            target_state="failed",
        )


def test_approved_cannot_go_directly_to_succeeded() -> None:
    with pytest.raises(InvalidActionTransitionError):
        validate_action_transition(
            current_state="approved",
            target_state="succeeded",
        )


def test_approved_cannot_go_directly_to_failed() -> None:
    with pytest.raises(InvalidActionTransitionError):
        validate_action_transition(
            current_state="approved",
            target_state="failed",
        )


def test_rejected_cannot_be_executed() -> None:
    with pytest.raises(InvalidActionTransitionError):
        validate_action_transition(
            current_state="rejected",
            target_state="executing",
        )


def test_rejected_cannot_be_approved() -> None:
    with pytest.raises(InvalidActionTransitionError):
        validate_action_transition(
            current_state="rejected",
            target_state="approved",
        )


def test_succeeded_cannot_execute_again() -> None:
    with pytest.raises(InvalidActionTransitionError):
        validate_action_transition(
            current_state="succeeded",
            target_state="executing",
        )


def test_succeeded_cannot_be_failed() -> None:
    with pytest.raises(InvalidActionTransitionError):
        validate_action_transition(
            current_state="succeeded",
            target_state="failed",
        )


def test_failed_cannot_succeed_without_retry() -> None:
    with pytest.raises(InvalidActionTransitionError):
        validate_action_transition(
            current_state="failed",
            target_state="succeeded",
        )


def test_failed_cannot_execute_again_without_retry() -> None:
    with pytest.raises(InvalidActionTransitionError):
        validate_action_transition(
            current_state="failed",
            target_state="executing",
        )
