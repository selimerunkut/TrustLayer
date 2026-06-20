FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_SYNC=1 \
    PATH="/app/.venv/bin:/root/.local/bin:${PATH}"

WORKDIR /app

COPY . .

ARG SOURCE_COMMIT=unknown

# Coolify may not populate SOURCE_COMMIT on the initial deploy path.
RUN uv sync --frozen --no-dev

ENV TRUSTLAYER_GIT_SHA="${SOURCE_COMMIT}" \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

ENTRYPOINT ["uv", "run", "--no-sync"]
