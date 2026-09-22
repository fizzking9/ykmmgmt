# ── Stage 1: dependencies ────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Bake the encoder weights into the image. Runtime loading is offline by default
# (EMBEDDING_ALLOW_DOWNLOAD=false): on a network where huggingface.co is blocked, a
# cold cache makes the first encode after startup retry with back-off for minutes.
# This runs on the CI/deploy runner, which can reach HF. Set BAKE_MODEL= to skip.
# HF_HOME is imported by sentence-transformers, so the cache layout must be shared
# between the bake step and the runtime stage.
ENV HF_HOME=/opt/models
ARG BAKE_MODEL=paraphrase-multilingual-MiniLM-L12-v2
RUN if [ -n "$BAKE_MODEL" ]; then \
        EMBEDDING_MODEL_NAME="$BAKE_MODEL" /opt/venv/bin/python -c 'import os; from sentence_transformers import SentenceTransformer; SentenceTransformer(os.environ["EMBEDDING_MODEL_NAME"]); print("baked encoder weights:", os.environ["EMBEDDING_MODEL_NAME"])'; \
    else \
        echo 'BAKE_MODEL empty - no weights baked'; \
    fi

# ── Stage 2: runtime ─────────────────────────────────────────────────────
FROM python:3.12-slim

# Unprivileged runtime user
RUN useradd --create-home --uid 1000 appuser

# Mirror the repo layout: backend at /app, runtime migrations at
# /runtime_migrations (alembic.ini resolves ../runtime_migrations from /app).
# The directory ships empty — dynamic tables are restored from DB reflection
# on startup; the version-controlled baseline migration in alembic/versions
# recreates them on fresh databases.
WORKDIR /app
RUN mkdir -p /runtime_migrations && chown -R appuser:appuser /runtime_migrations

COPY --from=builder /opt/venv /opt/venv
# Encoder weights from the bake stage, readable by the runtime user.
COPY --from=builder --chown=appuser:appuser /opt/models /opt/models
ENV PATH="/opt/venv/bin:$PATH" \
    HF_HOME=/opt/models \
    PYTHONUNBUFFERED=1

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
COPY main.py ./
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000
ENTRYPOINT ["docker-entrypoint.sh"]
