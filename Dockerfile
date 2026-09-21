# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync \
    --locked \
    --no-dev \
    --no-install-project

COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
COPY README.md ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync \
    --locked \
    --no-dev


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system app \
    && useradd --system \
       --gid app \
       --home-dir /app \
       app \
    && mkdir -p /app/data/documents \
    && chown -R app:app /app/data

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/migrations /app/migrations
COPY --from=builder /app/alembic.ini /app/alembic.ini

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

USER app

EXPOSE 8000

CMD ["uvicorn","ai_it_support_assistant.main:app","--host","0.0.0.0","--port","8000"]