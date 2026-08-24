FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (git required by gitpython)
RUN apt-get update && apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Install Poetry and uv
RUN pip install --no-cache-dir poetry uv && \
    poetry config virtualenvs.create false

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Install dependencies (no dev deps in production)
RUN poetry install --no-interaction --no-ansi --only main || \
    poetry install --no-interaction --no-ansi --only main --no-root

# Copy application
COPY app/ ./app/

# Create data directory
RUN mkdir -p /data/parquet

EXPOSE 8000

CMD ["python", "-m", "app.main"]
