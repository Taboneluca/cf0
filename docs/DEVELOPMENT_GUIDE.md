# Development Guide

This guide provides coding conventions, best practices, and patterns for extending CF0.

## Getting Started

### Prerequisites
- Node.js 18+ and npm/pnpm
- Python 3.11+
- Docker (for local Supabase)
- Git

### Initial Setup
```bash
# Clone repository
git clone https://github.com/yourusername/cf0.git
cd cf0

# Install dependencies
npm install
cd apps/api-gateway && pip install -r requirements.txt
cd ../frontend && npm install

# Setup environment
cp .env.example .env
# Edit .env with your API keys

# Start local Supabase
npx supabase start

# Run migrations
npx supabase db reset

# Start development servers
npm run dev
```

## Code Organization

### File Naming
- React components: `PascalCase.tsx`
- Hooks: `camelCase.ts` with `use` prefix
- Utilities: `kebab-case.ts`
- Python modules: `snake_case.py`

### Directory Structure
```
feature/
├── components/     # UI components
├── hooks/         # Feature-specific hooks
├── utils/         # Helper functions
├── types.ts       # TypeScript types
└── index.ts       # Public exports
```

## Frontend Development

### Component Patterns

#### Basic Component Structure
```typescript
import React from 'react';
import { cn } from '@/lib/utils';

interface ComponentProps {
  className?: string;
  children?: React.ReactNode;
  // ... other props
}

export function Component({ 
  className, 
  children, 
  ...props 
}: ComponentProps) {
  return (
    <div className={cn("base-styles", className)} {...props}>
      {children}
    </div>
  );
}
```

#### Component with State
```typescript
export function StatefulComponent() {
  const [state, setState] = useState<StateType>(initialState);
  
  // Event handlers
  const handleChange = useCallback((value: string) => {
    setState(prev => ({ ...prev, value }));
  }, []);
  
  // Effects
  useEffect(() => {
    // Side effects
    return () => {
      // Cleanup
    };
  }, [dependencies]);
  
  return <div>...</div>;
}
```

### Hook Patterns

#### Custom Hook Structure
```typescript
export function useCustomHook(initialValue: string) {
  const [value, setValue] = useState(initialValue);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  
  const execute = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const result = await apiCall();
      setValue(result);
    } catch (err) {
      setError(err as Error);
    } finally {
      setLoading(false);
    }
  }, []);
  
  return { value, loading, error, execute };
}
```

### State Management

#### Context Pattern
```typescript
interface ContextValue {
  state: StateType;
  actions: {
    updateValue: (value: string) => void;
    reset: () => void;
  };
}

const Context = createContext<ContextValue | null>(null);

export function Provider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  
  const actions = useMemo(() => ({
    updateValue: (value: string) => dispatch({ type: 'UPDATE', value }),
    reset: () => dispatch({ type: 'RESET' }),
  }), []);
  
  return (
    <Context.Provider value={{ state, actions }}>
      {children}
    </Context.Provider>
  );
}

export function useContext() {
  const context = useContext(Context);
  if (!context) {
    throw new Error('useContext must be used within Provider');
  }
  return context;
}
```

### API Integration

#### API Client Pattern
```typescript
class APIClient {
  private baseURL: string;
  
  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }
  
  async request<T>(
    endpoint: string, 
    options?: RequestInit
  ): Promise<T> {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });
    
    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`);
    }
    
    return response.json();
  }
  
  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' });
  }
  
  async post<T>(endpoint: string, data: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }
}

export const api = new APIClient('/api');
```

## Backend Development

### Agent Development

#### Creating a New Agent
```python
from agents.base_agent import BaseAgent
from typing import List, Dict, Any

class CustomAgent(BaseAgent):
    """Custom agent for specific tasks."""
    
    def default_prompt(self) -> str:
        return """You are a custom agent that helps with specific tasks.
        You have access to the following tools: {tools}
        """
    
    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "custom_tool",
                "description": "Does something custom",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "param": {"type": "string"}
                    },
                    "required": ["param"]
                },
                "function": self.custom_tool
            }
        ]
    
    async def custom_tool(self, param: str) -> Dict[str, Any]:
        """Implement custom tool logic."""
        return {"result": f"Processed: {param}"}
```

### Tool Development

#### Tool Function Pattern
```python
def spreadsheet_tool(
    cell_ref: str,
    value: Any = None,
    sheet: Spreadsheet = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Tool function with standard signature.
    
    Args:
        cell_ref: Cell reference (A1 notation)
        value: Optional value to set
        sheet: Spreadsheet instance
        **kwargs: Additional parameters
        
    Returns:
        dict: Result with status and data
    """
    try:
        # Validate inputs
        if not is_valid_cell_ref(cell_ref):
            return {"error": "Invalid cell reference"}
        
        # Perform operation
        if value is not None:
            old_value = sheet.get_cell(cell_ref)
            sheet.set_cell(cell_ref, value)
            
            return {
                "cell": cell_ref,
                "old_value": old_value,
                "new_value": value,
                "kind": "update"
            }
        else:
            return {
                "cell": cell_ref,
                "value": sheet.get_cell(cell_ref)
            }
            
    except Exception as e:
        return {"error": str(e)}
```

### LLM Provider Integration

#### Adding a New Provider
```python
from llm.base import LLMClient
from typing import AsyncGenerator

class NewProviderClient(LLMClient):
    """Client for new LLM provider."""
    
    def __init__(self, model: str = "default-model", api_key: str = None):
        self.model = model
        self.name = "newprovider"
        self.supports_tools = True
        self.supports_streaming = True
        self.client = NewProviderSDK(api_key=api_key)
    
    async def complete(
        self, 
        messages: List[Dict[str, str]], 
        **kwargs
    ) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs
        )
        return response.choices[0].message.content
    
    async def stream(
        self, 
        messages: List[Dict[str, str]], 
        **kwargs
    ) -> AsyncGenerator[str, None]:
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
            **kwargs
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
```

### API Endpoint Pattern

```python
@app.post("/api/resource/{id}")
async def update_resource(
    id: str,
    request: UpdateRequest,
    user=Depends(get_current_user)
):
    """
    Update a resource.
    
    Args:
        id: Resource identifier
        request: Update payload
        user: Authenticated user
        
    Returns:
        Updated resource
        
    Raises:
        HTTPException: On errors
    """
    try:
        # Validate permissions
        if not has_permission(user, id):
            raise HTTPException(403, "Permission denied")
        
        # Perform update
        resource = await get_resource(id)
        resource.update(request.dict())
        await save_resource(resource)
        
        return resource
        
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Error updating resource: {e}")
        raise HTTPException(500, "Internal server error")
```

## Testing

### Frontend Testing

#### Component Tests
```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { Component } from './Component';

describe('Component', () => {
  it('renders with props', () => {
    render(<Component title="Test" />);
    expect(screen.getByText('Test')).toBeInTheDocument();
  });
  
  it('handles user interaction', async () => {
    const handleClick = jest.fn();
    render(<Component onClick={handleClick} />);
    
    fireEvent.click(screen.getByRole('button'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});
```

#### Hook Tests
```typescript
import { renderHook, act } from '@testing-library/react';
import { useCustomHook } from './useCustomHook';

describe('useCustomHook', () => {
  it('updates value', () => {
    const { result } = renderHook(() => useCustomHook('initial'));
    
    act(() => {
      result.current.setValue('updated');
    });
    
    expect(result.current.value).toBe('updated');
  });
});
```

### Backend Testing

#### Unit Tests
```python
import pytest
from spreadsheet_engine.operations import set_cell
from spreadsheet_engine.model import Spreadsheet

class TestOperations:
    @pytest.fixture
    def sheet(self):
        return Spreadsheet(rows=10, cols=10)
    
    def test_set_cell(self, sheet):
        result = set_cell("A1", 42, sheet)
        assert result["new_value"] == 42
        assert sheet.get_cell("A1") == 42
    
    def test_invalid_cell_ref(self, sheet):
        with pytest.raises(ValueError):
            set_cell("ZZ999", 42, sheet)
```

#### Integration Tests
```python
@pytest.mark.asyncio
class TestAgent:
    async def test_agent_execution(self):
        agent = AskAgent(mock_llm_client())
        result = await agent.run(
            "What is the sum of column A?",
            history=[]
        )
        
        assert "reply" in result
        assert isinstance(result["reply"], str)
```

## Common Patterns

### Error Handling

#### Frontend Error Boundary
```typescript
class ErrorBoundary extends Component {
  state = { hasError: false, error: null };
  
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  
  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);
  }
  
  render() {
    if (this.state.hasError) {
      return <ErrorFallback error={this.state.error} />;
    }
    
    return this.props.children;
  }
}
```

#### Backend Error Handler
```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred",
            "type": type(exc).__name__,
            "request_id": request.state.request_id
        }
    )
```

### Performance Optimization

#### React Memoization
```typescript
const ExpensiveComponent = memo(({ data }: Props) => {
  const processedData = useMemo(() => 
    expensiveProcessing(data), 
    [data]
  );
  
  const handleClick = useCallback((id: string) => {
    // Handle click
  }, []);
  
  return <div>...</div>;
});
```

#### Backend Caching
```python
from functools import lru_cache
import asyncio

@lru_cache(maxsize=100)
def expensive_calculation(param: str) -> Any:
    """Cache expensive calculations."""
    return compute_result(param)

# Async cache
cache = {}
cache_lock = asyncio.Lock()

async def get_cached_data(key: str) -> Any:
    async with cache_lock:
        if key not in cache:
            cache[key] = await fetch_data(key)
        return cache[key]
```

## Debugging

### Frontend Debugging

```typescript
// Development-only logs
if (process.env.NODE_ENV === 'development') {
  console.log('Debug info:', { state, props });
}

// Performance profiling
console.time('expensive-operation');
performExpensiveOperation();
console.timeEnd('expensive-operation');

// React DevTools profiler
<Profiler id="Component" onRender={onRenderCallback}>
  <Component />
</Profiler>
```

### Backend Debugging

```python
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Debug decorator
def debug_timing(func):
    async def wrapper(*args, **kwargs):
        start = datetime.now()
        result = await func(*args, **kwargs)
        duration = (datetime.now() - start).total_seconds()
        logger.debug(f"{func.__name__} took {duration:.2f}s")
        return result
    return wrapper
```

## Deployment

### Pre-deployment Checklist
- [ ] All tests passing
- [ ] No console errors in production build
- [ ] Environment variables configured
- [ ] Database migrations ready
- [ ] API documentation updated
- [ ] Performance benchmarks met

### Deployment Commands
```bash
# Frontend (Vercel)
vercel --prod

# Backend (Railway)
railway up

# Database (Supabase)
supabase db push
```

## Common Pitfalls

1. **State Mutations** - Always create new objects/arrays
2. **Missing Dependencies** - Include all deps in useEffect
3. **N+1 Queries** - Use batch operations
4. **Memory Leaks** - Clean up subscriptions/timers
5. **Type Safety** - Don't use `any` unnecessarily
6. **Error Swallowing** - Always log errors
7. **Hardcoded Values** - Use environment variables

## Resources

- [React Documentation](https://react.dev)
- [Next.js Documentation](https://nextjs.org/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Supabase Documentation](https://supabase.com/docs)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/) 