#!/bin/bash

# Railway startup script for CF0 API Gateway with LangServe
# Uses main.py with integrated LangServe functionality for maximum compatibility

# Default to port 8000 if PORT is not set
PORT=${PORT:-8000}

echo "Starting CF0 API Gateway with LangServe on port $PORT"
echo "Working directory: $(pwd)"
echo "Python path: $PYTHONPATH"
echo "Environment: $RAILWAY_ENVIRONMENT_NAME"

# Use main.py with integrated LangServe functionality
echo "Starting server with LangServe-enhanced main.py..."
exec uvicorn main:app \
    --host 0.0.0.0 \
    --port $PORT \
    --workers 1 \
    --access-log \
    --log-level info 