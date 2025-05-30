#!/bin/bash

# Enable Debug Logging for Streaming Tool Calls
# This script sets all necessary environment variables for comprehensive debugging

echo "🔍 Enabling comprehensive debug logging for streaming tool calls..."

# Backend API Gateway Debugging
export DEBUG_STREAMING=1
export DEBUG_STREAMING_DELTA=1
export DEBUG_STREAMING_TOOLS=1
export DEBUG_FORMULA_PARSING=1

# Frontend Debugging (for Next.js)
export NEXT_PUBLIC_DEBUG_STREAMING=1
export NEXT_PUBLIC_DEBUG_SSE=1
export NEXT_PUBLIC_DEBUG_TOOLS=1

# Create .env file for frontend
cat > apps/frontend/.env.local << EOF
NEXT_PUBLIC_DEBUG_STREAMING=1
NEXT_PUBLIC_DEBUG_SSE=1
NEXT_PUBLIC_DEBUG_TOOLS=1
EOF

# Create .env file for API gateway
cat > apps/api-gateway/.env.debug << EOF
DEBUG_STREAMING=1
DEBUG_STREAMING_DELTA=1
DEBUG_STREAMING_TOOLS=1
DEBUG_FORMULA_PARSING=1
MAX_TOOL_ITERATIONS=10
MAX_RESPONSE_TOKENS=2000
EOF

echo "✅ Debug logging enabled!"
echo ""
echo "🚀 To start debugging:"
echo "1. Backend: cd apps/api-gateway && source .env.debug && python -m uvicorn api.main:app --reload --port 8000"
echo "2. Frontend: cd apps/frontend && npm run dev"
echo ""
echo "🔍 Debug Categories:"
echo "  🤖 Backend Streaming: [StreamingToolCallHandler], [stream-agent-*]"
echo "  🌐 Frontend Streaming: [STREAM_START], [SSE_EVENT], [TOOL_UPDATE]"
echo "  🔧 Tool Execution: [TOOL_START], [TOOL_COMPLETE], [TOOL_ERROR]"
echo "  📊 Performance: Chunk statistics, timing data"
echo ""
echo "🎯 Key Areas to Monitor:"
echo "  - Empty argument detection in StreamingToolCallHandler"
echo "  - Tool call completion signals"
echo "  - Retry manager behavior"
echo "  - Frontend SSE event parsing"
echo "  - Tool execution validation"
echo ""
echo "📝 To reproduce the issue:"
echo "  1. Open frontend in browser"
echo "  2. Try both 'ask' and 'analyst' modes"
echo "  3. Make broad requests like 'create a financial model'"
echo "  4. Watch console logs for empty tool calls or infinite loops"
echo ""
echo "🐛 Common Issues to Look For:"
echo "  - 'Empty arguments provided' errors"
echo "  - JSON parse errors in tool calls"
echo "  - Infinite retry loops"
echo "  - Missing tool call completion signals"
echo "  - Frontend SSE parsing failures" 