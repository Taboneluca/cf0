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
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:$PYTHONPATH \
    DEFAULT_MODEL="openai:gpt-4o-mini"

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 