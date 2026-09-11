from ai_it_support_assistant.schemas.approval import ActionState


class InvalidActionTransitionError(Exception):
    pass


ALLOWED_TRANSITIONS: dict[ActionState, set[ActionState]] = {
    "pending": {
        "approved",
        "rejected",
    },
    "approved": {
        "executing",
    },
    "executing": {
        "succeeded",
        "failed",
    },
    "succeeded": set(),
    "failed": set(),
    "rejected": set(),
}


def validate_action_transition(
    *,
    current_state: ActionState,
    target_state: ActionState,
) -> None:
    allowed = ALLOWED_TRANSITIONS[current_state]

    if target_state not in allowed:
        raise InvalidActionTransitionError(
            f"Invalid action transition: {current_state} -> {target_state}"
        )
