import logging
import time
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from ai_it_support_assistant.observability.logging_context import (
    reset_request_id,
    set_request_id,
)
from ai_it_support_assistant.observability.metrics import (
    HTTP_REQUEST_DURATION,
    HTTP_REQUESTS,
)

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next,
    ):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())

        token = set_request_id(request_id)

        start_time = time.perf_counter()

        status_code = 500

        logger.info(
            "request_started method=%s path=%s",
            request.method,
            request.url.path,
        )

        try:
            response = await call_next(request)

            status_code = response.status_code

            duration_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                ("request_completed method=%s path=%s status_code=%s duration_ms=%.2f"),
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )

            response.headers["X-Request-ID"] = request_id

            return response

        except Exception:
            duration_ms = (time.perf_counter() - start_time) * 1000

            logger.exception(
                ("request_failed method=%s path=%s duration_ms=%.2f"),
                request.method,
                request.url.path,
                duration_ms,
            )

            raise

        finally:
            if request.url.path != "/metrics":
                duration_seconds = time.perf_counter() - start_time

                route = request.scope.get("route")

                route_template = (
                    getattr(
                        route,
                        "path",
                        None,
                    )
                    or "unmatched"
                )

                status_class = f"{status_code // 100}xx"

                HTTP_REQUESTS.labels(
                    method=request.method,
                    route=route_template,
                    status_class=status_class,
                ).inc()

                HTTP_REQUEST_DURATION.labels(
                    method=request.method,
                    route=route_template,
                ).observe(duration_seconds)

            reset_request_id(token)
