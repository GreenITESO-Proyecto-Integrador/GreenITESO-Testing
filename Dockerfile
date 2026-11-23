FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY . .
RUN find /app -type f -name '*.py' -exec chmod 0644 {} +

RUN uv run playwright install --with-deps chromium

ENTRYPOINT ["uv", "run", "pytest"]
CMD ["--collect-only", "-q", "tests/Dashboard/test_Dashboard.py"]
