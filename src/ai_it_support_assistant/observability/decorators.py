import inspect
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

from ai_it_support_assistant.observability.metrics import (
    MCP_RESOURCE_READS,
    MCP_TOOL_CALLS,
    MCP_TOOL_DURATION,
)


def observe_mcp_tool(
    tool_name: str,
):
    def decorator(
        func: Callable[..., Any],
    ):
        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(
                *args: Any,
                **kwargs: Any,
            ):
                start = time.monotonic()
                outcome = "error"

                try:
                    result = await func(
                        *args,
                        **kwargs,
                    )

                    outcome = "success"
                    return result

                finally:
                    MCP_TOOL_CALLS.labels(
                        tool=tool_name,
                        outcome=outcome,
                    ).inc()

                    MCP_TOOL_DURATION.labels(
                        tool=tool_name,
                    ).observe(time.monotonic() - start)

            return async_wrapper

        @wraps(func)
        def sync_wrapper(
            *args: Any,
            **kwargs: Any,
        ):
            start = time.monotonic()
            outcome = "error"

            try:
                result = func(
                    *args,
                    **kwargs,
                )

                outcome = "success"
                return result

            finally:
                MCP_TOOL_CALLS.labels(
                    tool=tool_name,
                    outcome=outcome,
                ).inc()

                MCP_TOOL_DURATION.labels(
                    tool=tool_name,
                ).observe(time.monotonic() - start)

        return sync_wrapper

    return decorator


def observe_mcp_resource(
    resource_type: str,
):
    def decorator(
        func: Callable[..., Any],
    ):
        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(
                *args: Any,
                **kwargs: Any,
            ):
                outcome = "error"

                try:
                    result = await func(
                        *args,
                        **kwargs,
                    )

                    outcome = "success"
                    return result

                finally:
                    MCP_RESOURCE_READS.labels(
                        resource_type=resource_type,
                        outcome=outcome,
                    ).inc()

            return async_wrapper

        @wraps(func)
        def sync_wrapper(
            *args: Any,
            **kwargs: Any,
        ):
            outcome = "error"

            try:
                result = func(
                    *args,
                    **kwargs,
                )

                outcome = "success"
                return result

            finally:
                MCP_RESOURCE_READS.labels(
                    resource_type=resource_type,
                    outcome=outcome,
                ).inc()

        return sync_wrapper

    return decorator
