# Frontend Structure Guide

This guide explains the Next.js 14 frontend architecture, component hierarchy, and development patterns.

## Directory Structure

```
apps/frontend/
├── app/                    # Next.js 14 App Router
├── components/             # Reusable UI components  
├── context/               # React Context providers
├── hooks/                 # Custom React hooks
├── lib/                   # External library configs
├── types/                 # TypeScript type definitions
├── utils/                 # Helper functions
└── public/                # Static assets
```

## App Router Structure

### Pages
```
app/
├── (auth)/               # Auth group layout
│   ├── login/           # Login page
│   └── register/        # Registration page
├── dashboard/           # Main dashboard
├── workbook/
│   └── [id]/           # Dynamic workbook pages
├── api/                # API routes
└── layout.tsx          # Root layout
```

### API Routes
```
app/api/
├── langserve/
│   └── chat/           # SSE streaming proxy
├── workbooks/
│   └── [wid]/
│       └── sheets/
│           └── [sid]/
│               ├── apply/    # Apply updates
│               └── reject/   # Reject updates
└── auth/               # Auth endpoints
```

## Component Architecture

### Core Components

#### SpreadsheetInterface
Main spreadsheet UI container with grid, toolbar, and chat panel.
```typescript
<SpreadsheetInterface
  initialData={spreadsheetData}
  onDataChange={handleDataChange}
  readOnly={false}
  workbookControls={workbookControls}
/>
```

#### ChatInterface
AI chat panel with streaming support and pending updates.
```typescript
<ChatInterface
  messages={messages}
  setMessages={setMessages}
  mode={mode}
  setMode={setMode}
  isMinimized={isMinimized}
  toggleMinimize={toggleMinimize}
/>
```

#### SpreadsheetView
The actual grid component with cell rendering and selection.
```typescript
<SpreadsheetView
  data={data}
  selectedCell={selectedCell}
  onCellSelect={handleCellSelect}
  onCellEdit={handleCellEdit}
/>
```

### Component Hierarchy
```
SpreadsheetInterface
├── ToolbarRibbon
├── FormulaBar
├── SpreadsheetView
│   ├── Cell (virtualized)
│   └── SelectionOverlay
├── SheetTabs
└── ChatInterface
    ├── MessageBubble
    ├── PendingBar
    └── ModelSelect
```

## State Management

### Context Providers

#### WorkbookContext
Global workbook state and operations.
```typescript
const [wb, dispatch] = useWorkbook();

// State shape
{
  wid: string;
  sheets: string[];
  active: string;
  data: Record<string, SpreadsheetData>;
  formula: FormulaEdit;
  selected?: string;
  range?: RangeSelection;
}

// Actions
dispatch({ type: "UPDATE_SHEET", sid, data });
dispatch({ type: "SELECT_CELL", cell: "A1" });
dispatch({ type: "START_RANGE", sheet, anchor });
```

#### ModelContext
LLM model selection state.
```typescript
const { model, setModel } = useModel();
```

#### EditingContext
Cell editing and formula state.
```typescript
const { editingCell, setEditingCell, editingValue, setEditingValue } = useEditing();
```

### Local State Patterns

Components use local state for UI-specific concerns:
```typescript
// Resize state
const [chatWidth, setChatWidth] = useState(400);
const [isResizing, setIsResizing] = useState(false);

// Selection state
const [selectedCells, setSelectedCells] = useState<Set<string>>(new Set());
```

## Hooks Architecture

### useChatStreamSSE
Handles SSE streaming for chat responses.
```typescript
const {
  sendMessage,
  cancelStream,
  isStreaming,
  pendingUpdates,
  applyPendingUpdates,
  rejectPendingUpdates
} = useChatStreamSSE(setMessages, mode);
```

### useLocalStorage
Persists data to browser storage.
```typescript
const [savedValue, setSavedValue] = useLocalStorage('key', defaultValue);
```

### useSupabaseSession
Manages authentication state.
```typescript
const { user, session, loading } = useSupabaseSession();
```

## Data Flow Patterns

### 1. User Input Flow
```
User types in cell
→ EditingContext updates
→ onBlur triggers save
→ WorkbookContext dispatch
→ API call to backend
→ Optimistic UI update
```

### 2. Chat Streaming Flow
```
User sends message
→ useChatStreamSSE.sendMessage
→ SSE connection established
→ Events update local state
→ UI re-renders progressively
→ Pending updates accumulated
→ User applies/rejects changes
```

### 3. Formula Evaluation Flow
```
User types formula
→ FormulaBar captures input
→ Parse formula references
→ Highlight referenced cells
→ On Enter, send to backend
→ Update cell with result
```

## UI/UX Patterns

### 1. Responsive Design
- Breakpoints: sm (640px), md (768px), lg (1024px)
- Mobile-first approach
- Collapsible panels for small screens

### 2. Dark Mode
- CSS variables for theming
- Tailwind dark: prefix
- System preference detection

### 3. Loading States
```typescript
// Skeleton loaders
{loading && <Skeleton className="h-[400px]" />}

// Inline spinners
{isProcessing && <Loader2 className="animate-spin" />}

// Progress indicators
<Progress value={progress} />
```

### 4. Error Handling
```typescript
// Toast notifications
toast.error("Failed to save changes");

// Inline errors
{error && <Alert variant="destructive">{error}</Alert>}

// Error boundaries
<ErrorBoundary fallback={<ErrorFallback />}>
  <Component />
</ErrorBoundary>
```

## Performance Optimizations

### 1. React Optimizations
- Memo components that receive stable props
- useCallback for event handlers
- useMemo for expensive computations

### 2. Virtualization
Large spreadsheets use react-window:
```typescript
<VariableSizeGrid
  height={height}
  width={width}
  rowCount={rowCount}
  columnCount={columnCount}
  rowHeight={getRowHeight}
  columnWidth={getColumnWidth}
>
  {Cell}
</VariableSizeGrid>
```

### 3. Code Splitting
Dynamic imports for heavy components:
```typescript
const ChartComponent = dynamic(() => import('./ChartComponent'), {
  loading: () => <Skeleton />,
  ssr: false
});
```

### 4. Image Optimization
Next.js Image component:
```typescript
<Image
  src="/logo.png"
  alt="Logo"
  width={100}
  height={100}
  priority
/>
```

## Development Patterns

### 1. TypeScript Best Practices
```typescript
// Define explicit types
interface CellProps {
  value: string;
  onChange: (value: string) => void;
  readOnly?: boolean;
}

// Use discriminated unions
type CellUpdate = 
  | { type: 'value'; value: string }
  | { type: 'formula'; formula: string }
  | { type: 'style'; style: CellStyle };
```

### 2. Component Patterns
```typescript
// Compound components
<Spreadsheet>
  <Spreadsheet.Toolbar />
  <Spreadsheet.Grid />
  <Spreadsheet.StatusBar />
</Spreadsheet>

// Render props
<DataProvider
  render={({ data, loading }) => (
    loading ? <Loader /> : <Grid data={data} />
  )}
/>
```

### 3. Testing Patterns
```typescript
// Component testing
describe('Cell', () => {
  it('renders value', () => {
    render(<Cell value="A1" />);
    expect(screen.getByText('A1')).toBeInTheDocument();
  });
});

// Hook testing
const { result } = renderHook(() => useLocalStorage('key', 'default'));
act(() => {
  result.current[1]('new value');
});
expect(result.current[0]).toBe('new value');
```

## Common Pitfalls

1. **Avoid prop drilling** - Use context for deeply nested data
2. **Don't mutate state** - Always create new objects/arrays
3. **Handle SSR carefully** - Check for window/document
4. **Manage effect dependencies** - Include all used values
5. **Prevent memory leaks** - Clean up listeners/timers 