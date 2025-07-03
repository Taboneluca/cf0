# API Gateway Cleanup Recommendations
*Generated: Jan 2025*

## Executive Summary

Based on analysis of recent git commits and current codebase state, this document provides detailed recommendations for cleaning up the API gateway codebase. The recent migration to LangServe has left deprecated code and inconsistent patterns that should be addressed.

## Recent Git History Analysis

### Key Recent Changes
1. **LangServe Migration** (commits 352b24d - affd484)
   - Migrated from legacy SSE to LangServe pipeline
   - Removed standalone `serve.py`, integrated into `main.py`
   - Fixed 422 validation errors with input wrapper format
   - Upgraded langchain to 0.3.x

2. **Streaming Improvements** (commits 7389edb - 56320dc)
   - Replaced EventSource with fetch+ReadableStream
   - Implemented time-based batching
   - Fixed OpenAI GPT-4o streaming problems
   - Added flushSync for immediate rendering

## 1. Files to Delete

### Deprecated Endpoints
**File**: `apps/api-gateway/main.py`
- **Lines**: 231-239
- **What**: `/chat` and `/chat/stream` endpoints
- **Why**: Replaced by LangServe endpoints (`/ask/stream`, `/analyst/stream`)
- **Action**: Remove these endpoints completely, they just return 410 status

### Deprecated Legacy Endpoints
**File**: `apps/api-gateway/main.py`
- **Lines**: 242-297
- **What**: Old `/sheet`, `/sheet/update`, `/sheet/new`, `/session/reset` endpoints
- **Why**: Replaced by workbook-based endpoints
- **Action**: Delete entirely - already marked as deprecated

### Obsolete Test Files
- **File**: `apps/api-gateway/test_validation_simple.py`
- **Why**: Redundant with `test_langserve_validation.py`
- **Action**: Delete

### Temporary Debug Files
- **File**: `apps/api-gateway/debug_langserve.py`
- **Why**: Was created for debugging 422 errors, now resolved
- **Action**: Move useful utilities to a proper debugging module or delete

## 2. Code Refactoring Recommendations

### A. Consolidate Request Models
**Current Issue**: Multiple request model definitions scattered across files

**Files Affected**:
- `apps/api-gateway/main.py` (lines 650-668): `LangServeRequest`, `LangServeInputWrapper`
- `apps/api-gateway/api/schemas.py`: `ChatRequest`

**Recommendation**:
1. Create `apps/api-gateway/models/requests.py`
2. Consolidate all request models in one place
3. Use inheritance to reduce duplication:

```python
# models/requests.py
from pydantic import BaseModel
from typing import Optional, List

class BaseStreamRequest(BaseModel):
    mode: str
    message: str
    wid: str = "default"
    sid: str = "Sheet1"
    contexts: List[str] = []
    model: Optional[str] = None

class LangServeRequest(BaseStreamRequest):
    pass

class LangServeInputWrapper(BaseModel):
    input: LangServeRequest
```

### B. Extract LangServe Integration
**Current Issue**: LangServe code mixed with main application logic

**Files Affected**:
- `apps/api-gateway/main.py` (lines 650-825)

**Recommendation**:
1. Create `apps/api-gateway/langserve/__init__.py`
2. Move all LangServe-specific code:
   - Request/Response models
   - Stream wrapper functions
   - Route registration
3. Import and register in main.py

### C. Cleanup Streaming Implementation
**Current Issue**: Complex streaming logic with multiple wrapper layers

**Files Affected**:
- `apps/api-gateway/main.py` (lines 670-787)
- `apps/api-gateway/api/router.py` (process_message_streaming)

**Recommendation**:
1. Create `apps/api-gateway/streaming/handlers.py`
2. Implement clean separation:
   - SSE formatting layer
   - LangServe compatibility layer
   - Core streaming logic
3. Remove redundant debug logging in production

### D. Tool Functions Refactoring
**Current Issue**: Tool function wrapping logic repeated multiple times

**Files Affected**:
- `apps/api-gateway/main.py` (lines 380-542)
- `apps/api-gateway/api/router.py` (lines 148-449)

**Recommendation**:
1. Create `apps/api-gateway/tools/wrappers.py`
2. Extract common patterns:
   - Cell reference validation
   - Cross-sheet reference handling
   - Parameter name flexibility (cell vs cell_ref)
3. Create factory functions for tool wrapping

## 3. Configuration Management

### Current Issues
- Environment variables scattered throughout code
- No central configuration management
- Mixed use of os.getenv() with different defaults

### Recommendation
Create `apps/api-gateway/config.py`:

```python
from pydantic import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # LLM
    llm_concurrency: int = 5
    default_model: Optional[str] = None
    
    # Features
    enable_template_tools: bool = False
    debug_streaming: bool = False
    
    # External Services
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None
    
    class Config:
        env_file = ".env"

settings = Settings()
```

## 4. Error Handling Standardization

### Current Issues
- Inconsistent error responses
- Mixed use of HTTPException and custom error dicts
- Validation errors not properly formatted

### Recommendation
Create `apps/api-gateway/exceptions.py`:

```python
from fastapi import HTTPException
from typing import Dict, Any

class SpreadsheetException(HTTPException):
    def __init__(self, status_code: int, error_code: str, message: str, details: Dict[str, Any] = None):
        super().__init__(
            status_code=status_code,
            detail={
                "error": error_code,
                "message": message,
                "details": details or {}
            }
        )

class SheetNotFoundError(SpreadsheetException):
    def __init__(self, wid: str, sid: str):
        super().__init__(
            status_code=404,
            error_code="SHEET_NOT_FOUND",
            message=f"Sheet {sid} not found in workbook {wid}"
        )
```

## 5. Testing Infrastructure

### Current State
- Multiple test files with overlapping functionality
- No organized test structure
- Missing integration tests for new LangServe endpoints

### Recommendation
Reorganize tests:

```
apps/api-gateway/tests/
├── unit/
│   ├── test_models.py
│   ├── test_tools.py
│   └── test_streaming.py
├── integration/
│   ├── test_langserve_endpoints.py
│   ├── test_workbook_operations.py
│   └── test_streaming_flow.py
└── conftest.py  # Shared fixtures
```

## 6. Documentation Updates

### Files to Update
1. **README.md**: Remove references to deprecated endpoints
2. **LANGSERVE_DEPLOYMENT.md**: Update with current implementation
3. Add **API_REFERENCE.md**: Document all current endpoints

### New Documentation Needed
1. **STREAMING_ARCHITECTURE.md**: Explain the streaming pipeline
2. **MODEL_SELECTION.md**: Document model selection and configuration
3. **MIGRATION_GUIDE.md**: Help users migrate from old endpoints

## 7. Performance Optimizations

### Current Issues
1. WebSocket handler creates new tool functions for each connection
2. No connection pooling for LLM clients
3. Repeated sheet summary calculations

### Recommendations
1. Cache tool function instances
2. Implement LLM client connection pooling
3. Add caching layer for sheet summaries with invalidation

## 8. Security Improvements

### Current Issues
1. CORS allows all origins in production
2. No rate limiting on streaming endpoints
3. Missing authentication on some endpoints

### Recommendations
1. Configure CORS properly for production
2. Implement rate limiting middleware
3. Add authentication middleware for all data endpoints

## Implementation Priority

### Phase 1 (Immediate)
1. Delete deprecated endpoints and files
2. Extract LangServe integration
3. Consolidate request models

### Phase 2 (Short-term)
1. Refactor tool functions
2. Implement configuration management
3. Standardize error handling

### Phase 3 (Medium-term)
1. Reorganize test structure
2. Update documentation
3. Implement performance optimizations

### Phase 4 (Long-term)
1. Security improvements
2. Monitoring and observability
3. Advanced caching strategies

## Conclusion

The codebase has evolved rapidly with the LangServe migration. While functional, it contains technical debt from the migration process. Following these recommendations will result in a cleaner, more maintainable codebase that's easier to extend and debug.