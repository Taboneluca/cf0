FROM python:3.12-slim

WORKDIR /app

# Install Poetry
RUN pip install poetry==1.8.2

# Configure poetry to not create a virtual environment
RUN poetry config virtualenvs.create false

# Copy pyproject.toml
COPY pyproject.toml poetry.lock* ./

# Install dependencies
RUN poetry install --no-dev

# Copy source code
COPY . .

# Environment variables for LLM providers
ENV OPENAI_API_KEY=$OPENAI_API_KEY
ENV ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY
ENV GROQ_API_KEY=$GROQ_API_KEY
ENV DEFAULT_MODEL="openai:gpt-4o-mini"

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 