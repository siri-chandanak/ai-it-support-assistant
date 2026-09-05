import logging
import time
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from ai_it_support_assistant.core.request_context import (
    request_id_context,
)

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next,
    ):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())

        token = request_id_context.set(request_id)

        start_time = time.perf_counter()

        logger.info(
            "request_started request_id=%s method=%s path=%s",
            request_id,
            request.method,
            request.url.path,
        )

        try:
            response = await call_next(request)

            duration_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                (
                    "request_completed "
                    "request_id=%s "
                    "method=%s "
                    "path=%s "
                    "status_code=%s "
                    "duration_ms=%.2f"
                ),
                request_id,
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
                ("request_failed request_id=%s method=%s path=%s duration_ms=%.2f"),
                request_id,
                request.method,
                request.url.path,
                duration_ms,
            )

            raise

        finally:
            request_id_context.reset(token)
