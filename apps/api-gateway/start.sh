#!/bin/bash

# Railway startup script for CF0 API Gateway
# Uses the existing working main.py instead of serve.py

# Default to port 8000 if PORT is not set
export PORT=${PORT:-8000}

echo "Starting CF0 API Gateway on port $PORT"
echo "Working directory: $(pwd)"
echo "Python path: $PYTHONPATH"
echo "Environment: $RAILWAY_ENVIRONMENT_NAME"

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Use the existing working main.py (has working /chat/stream endpoint)
echo "Starting server with existing main.py..."
exec python -m uvicorn main:app \
    --host 0.0.0.0 \
    --port $PORT \
    --workers 1 \
    --access-log \
    --log-level info 