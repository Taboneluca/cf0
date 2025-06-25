# LangServe Deployment Guide

## Overview

This deployment replaces the custom SSE streaming implementation with LangServe for robust, production-ready streaming. The new implementation provides:

- **Enhanced Streaming**: LangServe's battle-tested streaming infrastructure
- **Full Compatibility**: All existing endpoints and frontend compatibility maintained
- **Robust Error Handling**: Improved error recovery and circuit breakers
- **Better Performance**: Optimized streaming with proper buffering and flow control

## Key Changes

### 1. New Main Application (`serve.py`)
- Uses LangServe's `add_routes` for `/ask/*` and `/analyst/*` endpoints
- Maintains legacy `/chat/stream` endpoint for frontend compatibility
- Includes all tool functions and workbook context
- Proper CORS and middleware configuration

### 2. Updated Startup Script (`start.sh`)
- Now uses `serve.py` instead of `main.py`
- Same environment variable handling
- Railway-compatible port configuration

### 3. LangServe Features
- **Native Streaming**: `/ask/stream` and `/analyst/stream` endpoints
- **Blocking API**: `/ask/invoke` and `/analyst/invoke` endpoints  
- **Auto Documentation**: Built-in OpenAPI docs at `/docs`
- **Health Monitoring**: Enhanced health checks and metrics

## Endpoints

### LangServe Native Endpoints
- `POST /ask/stream` - Streaming ask mode
- `POST /ask/invoke` - Blocking ask mode
- `POST /analyst/stream` - Streaming analyst mode
- `POST /analyst/invoke` - Blocking analyst mode

### Legacy Compatibility
- `POST /chat/stream` - SSE format for existing frontend
- `POST /chat` - Blocking chat endpoint
- `GET /workbook/{wid}/sheet/{sid}` - Sheet data
- `POST /workbook/{wid}/sheet/{sid}/update` - Cell updates
- `GET /models` - Available models

## Deployment

The deployment is ready to go:

1. **Railway**: Uses the updated `start.sh` which points to `serve.py`
2. **Environment**: Same environment variables as before
3. **Dependencies**: LangServe already in `requirements.txt`

## Frontend Compatibility

The frontend requires **NO CHANGES**:
- `/chat/stream` endpoint maintained with SSE format
- All response formats preserved
- Same request/response schemas
- Existing error handling works unchanged

## Benefits

### Performance
- Reduced memory usage during streaming
- Better connection management
- Improved error recovery

### Reliability
- LangServe's proven streaming infrastructure
- Built-in retry mechanisms
- Better timeout handling

### Monitoring
- Enhanced logging with request IDs
- Performance metrics
- Health check improvements

## Testing

The implementation has been designed to work immediately with:
- Existing frontend code
- Current environment configuration  
- All existing chat modes (ask/analyst)
- Tool functions and workbook operations

Deploy and test - the system should work seamlessly with improved streaming performance. 