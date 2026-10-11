# The app only serves the web UI. Models run elsewhere: Ollama on another machine
# (set OLLAMA_HOST) and/or the Claude API (set ANTHROPIC_API_KEY). No models in the image.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first, so code changes don't invalidate this layer.
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

# Run as a non-root user. UID 1000 matches the first user on most Linux machines,
# so files written to a bind-mounted saves folder stay owned by you.
RUN useradd --uid 1000 --create-home fiction \
    && mkdir -p /data/saves \
    && chown fiction:fiction /data/saves
USER fiction

ENV PATH="/app/.venv/bin:$PATH" \
    HOST=0.0.0.0 \
    PORT=8000 \
    FICTION_SAVES_DIR=/data/saves

EXPOSE 8000
VOLUME ["/data/saves"]

CMD ["fiction"]
