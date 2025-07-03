#!/bin/bash
# Railway startup script for CF0 API Gateway
# Uses main.py with SSE streaming functionality

# Set the port from Railway environment or default to 8000
PORT=${PORT:-8000}

echo "Starting CF0 API Gateway on port $PORT"

# Ensure all required environment variables are available
echo "Environment check:"
echo "  DATABASE_URL: ${DATABASE_URL:0:20}..."

# Use main.py with SSE streaming functionality
echo "Starting server with SSE-enhanced main.py..."

# Start the server using the main application
exec uvicorn main:app \
    --host 0.0.0.0 \
    --port $PORT \
    --workers 1 \
    --loop uvloop 