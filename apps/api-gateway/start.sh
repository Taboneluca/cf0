#!/bin/bash

# Railway startup script for CF0 API Gateway with LangServe
# Uses the new LangServe implementation for robust streaming

# Default to port 8000 if PORT is not set
export PORT=${PORT:-8000}

echo "Starting CF0 API Gateway with LangServe on port $PORT"
echo "Working directory: $(pwd)"
echo "Python path: $PYTHONPATH"
echo "Environment: $RAILWAY_ENVIRONMENT_NAME"

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Use the new LangServe implementation for robust streaming
echo "Starting server with LangServe (serve.py)..."
exec python -m uvicorn serve:app \
    --host 0.0.0.0 \
    --port $PORT \
    --workers 1 \
    --access-log \
    --log-level info 