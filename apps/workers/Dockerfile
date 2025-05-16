FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Poetry & configure
ENV POETRY_VERSION=1.8.2
RUN pip install "poetry==$POETRY_VERSION"
RUN poetry config virtualenvs.create false

# Copy lock files first to exploit Docker layer caching
COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-dev --no-interaction --no-ansi

# Copy source code last
COPY . .

# Runtime environment variables
ENV PYTHONUNBUFFERED=1

# Command to run the worker
CMD ["python", "worker.py"] 