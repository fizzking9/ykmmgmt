# ── Stage 1: dependencies ────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

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
ENV PATH="/opt/venv/bin:$PATH" \
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
