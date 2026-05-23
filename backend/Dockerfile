# syntax=docker/dockerfile:1

# ---- builder: resolve + install deps into a venv ----
FROM python:3.12-slim AS builder

# uv: fast, reproducible installs straight from uv.lock.
COPY --from=ghcr.io/astral-sh/uv:0.8.9 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install only third-party deps first so this layer caches across code changes.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Pre-download the embedding model so the first request isn't a cold start.
ENV PATH="/app/.venv/bin:$PATH" \
    HF_HOME=/opt/hf_cache
ARG EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
RUN python -c "from sentence_transformers import SentenceTransformer as S; S('${EMBEDDING_MODEL}')"

# ---- runtime: slim image with the prepared venv + model cache ----
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    HF_HOME=/opt/hf_cache \
    APP_ENV=production

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /opt/hf_cache /opt/hf_cache
COPY app ./app
COPY scripts ./scripts

# Run as a non-root user.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/uploads \
    && chown -R appuser:appuser /app /opt/hf_cache
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
