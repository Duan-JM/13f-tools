# syntax=docker/dockerfile:1.7
# Multi-stage Dockerfile for sec13f-analyzer.
# Builds the package with Poetry in a builder stage and produces a slim
# runtime image that runs the long-running `sec13f-cli monitor` service
# by default.

ARG PYTHON_VERSION=3.12
ARG POETRY_VERSION=2.1.3


# ---------------------------------------------------------------------------
# Builder: install Poetry, resolve dependencies, build the wheel.
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

ARG POETRY_VERSION

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=true \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_CACHE_DIR=/tmp/poetry-cache

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libxml2-dev \
        libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

# Install runtime dependencies first so Docker layers cache well.
COPY pyproject.toml poetry.lock README.md ./
RUN poetry install --only main --no-root

# Copy the source and install the project itself into the same venv.
COPY src ./src
RUN poetry install --only main \
    && rm -rf "$POETRY_CACHE_DIR"


# ---------------------------------------------------------------------------
# Runtime: minimal image with only the venv and the source tree.
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Runtime libraries needed by lxml / matplotlib at import time.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libxml2 \
        libxslt1.1 \
        tini \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user to run the service.
RUN groupadd --system --gid 1000 sec13f \
    && useradd --system --uid 1000 --gid sec13f --home /app --shell /usr/sbin/nologin sec13f

WORKDIR /app

# Copy resolved virtualenv and source from the builder stage.
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/pyproject.toml /app/pyproject.toml

# Mount points for user-supplied config and persistent monitor state.
RUN mkdir -p /app/config /app/state /app/output \
    && chown -R sec13f:sec13f /app

USER sec13f

VOLUME ["/app/config", "/app/state", "/app/output"]

# Tini reaps zombies and forwards SIGTERM/SIGINT to the monitor loop so
# the service shuts down cleanly under `docker stop` / compose.
ENTRYPOINT ["/usr/bin/tini", "--", "sec13f-cli"]
CMD ["monitor", "--config", "/app/config/monitor_config.yml"]
