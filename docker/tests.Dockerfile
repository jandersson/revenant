# The CI battery in a Linux container — build and run via
# tools/docker_tests.py. Linux is where CI runs and where the socket
# gotcha lives (closing a socket does not wake a blocked recv() there —
# CLAUDE.md), so Linux-only hangs surface here before a push. macOS
# cannot be containerized; the workflow's macos leg covers it (#84).
ARG PYTHON_VERSION=3.12
FROM ghcr.io/astral-sh/uv:python${PYTHON_VERSION}-bookworm-slim

# tzdata: the clocks/eltime tests resolve real zones (Europe/Stockholm),
# present on CI's ubuntu but not guaranteed in slim images (#67 was the
# same hole on Windows).
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV UV_LINK_MODE=copy

# Dependency layer: cached until the lock or a member manifest moves.
COPY pyproject.toml uv.lock ./
COPY client/pyproject.toml client/pyproject.toml
COPY chat/pyproject.toml chat/pyproject.toml
COPY beholder/pyproject.toml beholder/pyproject.toml
RUN uv sync --all-packages --no-install-workspace

# The workspace itself changes every edit; this layer stays cheap.
COPY . .
RUN uv sync --all-packages

# The same battery as .github/workflows/python-package.yml, same order.
CMD ["sh", "-ec", "\
    uv run ruff check client chat beholder; \
    uv run ruff format --check client chat beholder; \
    (cd client && uv run pytest); \
    (cd beholder && uv run pytest); \
    uv run pytest chat/tests"]
