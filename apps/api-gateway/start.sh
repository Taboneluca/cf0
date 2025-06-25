#!/bin/bash

# Railway startup script for CF0 API Gateway
# Handles PORT environment variable properly

# Default to port 8000 if PORT is not set
export PORT=${PORT:-8000}

echo "Starting CF0 API Gateway on port $PORT"
echo "Environment: $RAILWAY_ENVIRONMENT_NAME"
echo "Git commit: $RAILWAY_GIT_COMMIT_SHA"

# Install dependencies if needed
pip install -r requirements.txt

# Start the FastAPI server with LangServe endpoints
exec uvicorn apps.api_gateway.serve:app \
    --host 0.0.0.0 \
    --port $PORT \
    --workers 1 \
    --access-log \
    --log-level info 