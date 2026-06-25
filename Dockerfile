# Minimal, non-root image for the trace explorer / demo.
FROM python:3.12-slim

# uv for fast, reproducible installs from the committed lockfile.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first (cached layer), then the project.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY data ./data
RUN uv sync --frozen --no-dev

# Run as a non-root user.
RUN useradd --create-home --uid 10001 forensics \
    && chown -R forensics:forensics /app
USER forensics

EXPOSE 8501

# Default: launch the trace explorer. Override to run the demo:
#   docker run --rm <image> uv run python -m forensics.demo
CMD ["uv", "run", "streamlit", "run", "src/forensics/app/main.py", \
     "--server.address=0.0.0.0", "--server.port=8501"]
