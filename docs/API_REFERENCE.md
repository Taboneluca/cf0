# API Reference

Complete API documentation for CF0's REST and streaming endpoints.

## Base URLs

- **Production**: `https://api.cf0.ai`
- **Development**: `http://localhost:8000`

## Authentication

All API endpoints require authentication via Supabase session tokens.

### Headers
```
Authorization: Bearer <supabase_access_token>
Content-Type: application/json
```

## Core Endpoints

### Health Check

#### GET /health
Health check endpoint for monitoring.

**Response**
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

### Models

#### GET /models
Get available language models with capabilities.

**Response**
```json
[
  {
    "id": "gpt-4o",
    "name": "GPT-4 Omni",
    "provider": "openai",
    "capabilities": {
      "streaming": true,
      "functions": true,
      "vision": true
    }
  }
]
```

## Workbook Management

### Get Sheet Data

#### GET /workbook/{wid}/sheet/{sid}
Retrieve data for a specific sheet.

**Parameters**
- `wid` (path): Workbook ID
- `sid` (path): Sheet ID

**Response**
```json
{
  "sheet": {
    "cells": [[...]],
    "n_rows": 100,
    "n_cols": 26
  },
  "sheets": ["Sheet1", "Sheet2"],
  "active": "Sheet1"
}
```

### Update Cell

#### POST /workbook/{wid}/sheet/{sid}/update
Update a single cell value.

**Request Body**
```json
{
  "cell": "A1",
  "value": "New Value"
}
```

**Response**
```json
{
  "cell": "A1",
  "old_value": "Old Value",
  "new_value": "New Value",
  "kind": "normal",
  "sheet": {...},
  "all_sheets": {...}
}
```

### Create Sheet

#### POST /workbook/{wid}/sheet
Create a new sheet in the workbook.

**Request Body**
```json
{
  "name": "NewSheet",
  "rows": 100,
  "columns": 26
}
```

**Response**
```json
{
  "sheets": ["Sheet1", "NewSheet"],
  "active": "NewSheet",
  "sheet": {...}
}
```

### Apply Updates

#### POST /workbook/{wid}/sheet/{sid}/apply
Apply pending cell updates from streaming session.

**Request Body**
```json
{
  "updates": [
    {
      "cell": "A1",
      "value": 100,
      "old_value": 0,
      "kind": "normal"
    }
  ]
}
```

**Response**
```json
{
  "status": "success",
  "result": {...},
  "sheet": {...}
}
```

### Reject Updates

#### POST /workbook/{wid}/sheet/{sid}/reject
Reject pending updates and restore previous state.

**Response**
```json
{
  "status": "reverted",
  "sheet": {...}
}
```

## Streaming Endpoints

### Ask Mode (Read-Only)

#### POST /ask/stream
Stream AI responses for spreadsheet analysis without modifications.

**Request Body**
```json
{
  "message": "What is the sum of column A?",
  "wid": "workbook-id",
  "sid": "Sheet1",
  "model": "gpt-4o",
  "contexts": ["A1:A10"]
}
```

**Response**: Server-Sent Events stream

### Analyst Mode (Read-Write)

#### POST /analyst/stream
Stream AI responses with ability to modify spreadsheet.

**Request Body**
```json
{
  "message": "Calculate 20% increase for all values in column B",
  "wid": "workbook-id",
  "sid": "Sheet1",
  "model": "gpt-4o",
  "contexts": []
}
```

**Response**: Server-Sent Events stream

### SSE Event Format

Events follow the standard SSE format:
```
event: content
data: {"delta": "Calculating sum..."}

event: tool_call
data: {"tool": "get_range", "arguments": {"range": "A1:A10"}, "id": "call_123"}

event: tool_result
data: {"tool_id": "call_123", "result": {"values": [1,2,3,4,5]}}

event: update
data: {"updates": [{"cell": "B1", "old_value": 10, "new_value": 12}]}

event: done
data: {"status": "completed"}
```

## Error Responses

All endpoints use standard HTTP status codes and return errors in this format:

```json
{
  "detail": "Error message",
  "code": "ERROR_CODE",
  "context": {...}
}
```

### Common Error Codes
- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (missing/invalid auth)
- `404` - Not Found (resource doesn't exist)
- `422` - Validation Error (invalid request body)
- `500` - Internal Server Error

## Rate Limiting

- **LLM Requests**: 5 concurrent requests per user
- **API Calls**: 100 requests per minute
- **Streaming**: 1 active stream per session

## Request/Response Schemas

### ChatRequest
```typescript
interface ChatRequest {
  message: string;
  wid: string;
  sid: string;
  model: string;
  mode?: 'ask' | 'analyst';
  contexts?: string[];
}
```

### SheetUpdateRequest
```typescript
interface SheetUpdateRequest {
  cell: string;
  value: any;
}
```

### WorkbookState
```typescript
interface WorkbookState {
  wid: string;
  sheets: string[];
  active: string;
  data: Record<string, SpreadsheetData>;
}
```

## WebSocket Endpoint

### /chat/step
WebSocket endpoint for debug mode with step-by-step agent execution.

**Connection**
```javascript
const ws = new WebSocket('ws://localhost:8000/chat/step');
ws.send(JSON.stringify(chatRequest));
```

**Messages**
- Sends ChatStep objects for each agent action
- Final message: `{"status": "complete"}`

## Next.js API Routes

The frontend provides proxy routes for backend communication:

### POST /api/langserve/chat
Proxies streaming requests to backend with proper headers.

### POST /api/workbooks/{wid}/sheets/{sid}/apply
Proxies update application requests.

### POST /api/workbooks/{wid}/sheets/{sid}/reject
Proxies update rejection requests.

## Best Practices

1. **Always include workbook and sheet IDs** in requests
2. **Use streaming endpoints** for chat interactions
3. **Handle SSE reconnection** on connection loss
4. **Validate cell references** before sending
5. **Cache model list** as it rarely changes 