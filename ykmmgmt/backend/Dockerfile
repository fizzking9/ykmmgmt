# ── Stage 1: dependencies ────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .

# sentence-transformers depends on torch, and PyPI's default Linux wheel is the
# CUDA build: one 3.3GB layer of nvidia libraries. This container does CPU
# inference only (that is what the encoder benchmark measured) and the prod host
# pulls images over a modest uplink, so the whole file would have made releases
# take hours. PyTorch's CPU index is ~200MB. It is installed *before*
# requirements.txt so torch is already satisfied when pip resolves
# sentence-transformers and never reaches back to PyPI for the CUDA wheel.
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Drop the two torch directories that a runtime never loads: its test suite (85MB)
# and its build headers (63MB). Everything else in the package was tried and is
# genuinely imported: deleting torch/bin fails the bake with "Unable to find
# torch_shm_manager", and deleting torchgen fails it with "No module named
# 'torchgen'" -- which is exactly why the bake runs *after* this step. It is a real
# `import torch` + encode, so dead weight the runtime needs stops the build here
# instead of surfacing on the production host.
RUN SP=/opt/venv/lib/python3.12/site-packages \
    && rm -rf "$SP/torch/test" "$SP/torch/include" \
    && find /opt/venv -name '__pycache__' -type d -prune -exec rm -rf {} + \
    && du -sh /opt/venv

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
