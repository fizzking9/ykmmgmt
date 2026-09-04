# ── Stage 1: dependencies ────────────────────────────────────────────────
# pyproject.toml lives INSIDE the package (package-dir ".." resolves one
# level up, which is where the package sits inside this build context).
FROM python:3.12-slim AS builder

WORKDIR /build
COPY . /build/mcp_server
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir /build/mcp_server

# ── Stage 2: runtime ─────────────────────────────────────────────────────
FROM python:3.12-slim

# CJK fonts so matplotlib renders Chinese labels (the renderer's fallback
# chain finds "Noto Sans CJK SC" from this package) — without it, every
# Chinese character in a chart renders as a tofu box.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# Unprivileged runtime user
RUN useradd --create-home --uid 1000 appuser

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    # Writable matplotlib cache dir (appuser cannot write to system default)
    MPLCONFIGDIR=/tmp/matplotlib

USER appuser

EXPOSE 8001
# Starts the streamable-HTTP MCP server (uvicorn) — requires YKM_MCP_API_KEY
ENTRYPOINT ["ykmmgmt-mcp"]
