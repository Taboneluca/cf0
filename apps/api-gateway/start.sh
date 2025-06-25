#!/bin/bash

# Railway startup script for CF0 API Gateway
# Handles PORT environment variable and module path correctly

# Default to port 8000 if PORT is not set
export PORT=${PORT:-8000}

echo "Starting CF0 API Gateway on port $PORT"
echo "Working directory: $(pwd)"
echo "Python path: $PYTHONPATH"
echo "Environment: $RAILWAY_ENVIRONMENT_NAME"

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Since Railway root directory is /apps/api-gateway, 
# we need to use the correct module path
echo "Starting server with correct module path..."
exec python -m uvicorn serve:app \
    --host 0.0.0.0 \
    --port $PORT \
    --workers 1 \
    --access-log \
    --log-level info 