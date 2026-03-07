FROM python:3.12-slim

WORKDIR /app

# Install Poetry
RUN pip install --no-cache-dir poetry && \
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

EXPOSE 8080

CMD ["python", "-m", "app.main"]
