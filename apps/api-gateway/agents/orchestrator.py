from typing import Optional, Dict, Any, AsyncGenerator, List
import time
import json
import os
import inspect
import re

from llm.base import LLMClient
from llm.factory import get_client
from llm import wrap_stream_with_guard
from .analyst_agent import build as build_analyst_agent
from .ask_agent import build as build_ask_agent
from .base_agent import BaseAgent, ChatStep
from spreadsheet_engine.model import Spreadsheet
from spreadsheet_engine.summary import sheet_summary


class ContextAnalyzer:
    """
    Analyzes conversation context to understand what the user is referring to.
    This mirrors how Cursor and Windsurf understand context references.
    """
    
    @staticmethod
    def extract_implementation_context(history: List[Dict[str, Any]]) -> Optional[str]:
        """
        Extract actionable implementation details from conversation history.
        Looks for detailed specifications, requirements, or plans that can be executed.
        """
        if not history:
            return None
            
        # Enhanced patterns for financial and spreadsheet models
        context_patterns = [
            # Financial models and calculations
            r'(?i)(wacc|weighted average cost|discount rate|valuation|financial model)',
            r'(?i)(income statement|balance sheet|cash flow|p&l|profit)',
            r'(?i)(model|template|table|structure|format)',
            # Spreadsheet-specific patterns
            r'(?i)(cell|row|column|header|formula|calculation)',
            r'(?i)(A1|B1|C1|D1|A2|B2|C2|D2)',  # Cell references
            r'(?i)(=SUM|=AVERAGE|=MAX|=MIN|=[A-Z]+[0-9]+)',  # Excel formulas
            # Data specifications
            r'(?i)(rows?|columns?|cells?|data|fields?|headers?)',
            r'(?i)(calculate|compute|build|create|generate|set up)',
            # Detailed descriptions with steps
            r'(?i)(steps?|process|methodology|approach|structure)',
            r'(?i)(inputs?|outputs?|formula|calculation|equation)',
            # Financial statement specific
            r'(?i)(revenue|sales|expenses|costs|profit|loss|assets|liabilities|equity)',
            r'(?i)(gross profit|operating income|net income|total)'
        ]
        
        # Look for the most recent substantial message with implementation details
        best_context = None
        best_score = 0
        
        # Check last 15 messages instead of 10 to capture more context
        for message in reversed(history[-15:]):
            if message.get('role') == 'user':
                continue
                
            content = message.get('content', '')
            if len(content) < 100:  # Skip short messages
                continue
                
            # Count pattern matches to determine relevance
            pattern_matches = sum(1 for pattern in context_patterns if re.search(pattern, content))
            
            # Give extra weight to messages with cell references, formulas, or financial terms
            bonus_patterns = [
                r'(?i)(cell [A-Z][0-9]+|[A-Z][0-9]+:)',  # Cell references
                r'(?i)(=\w+\(|formula)',  # Excel formulas
                r'(?i)(income statement|balance sheet|cash flow)',  # Financial statements
                r'(?i)(header|column|row)',  # Spreadsheet structure
            ]
            bonus_score = sum(2 for pattern in bonus_patterns if re.search(pattern, content))
            
            total_score = pattern_matches + bonus_score
            
            # If message has good patterns and substantial content, consider it
            if total_score >= 3 and len(content) > 200:
                if total_score > best_score:
                    best_context = content
                    best_score = total_score
                    
        return best_context
    
    @staticmethod
    def analyze_user_intent(message: str, history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze user intent to determine if they're referring to previous context
        and what type of action they want to take.
        """
        message_lower = message.lower().strip()
        
        # Enhanced reference detection patterns
        reference_patterns = {
            'direct_reference': [
                r'(?i)\b(build|create|implement|make|generate|set up)\s+(the\s+)?(above|that|this|it)\b',
                r'(?i)\b(do|execute|perform|carry out)\s+(the\s+)?(above|that|this|it)\b',
                r'(?i)\b(based on|using|following)\s+(the\s+)?(above|previous|that|what)\b',
                r'(?i)\b(build|create|implement|make|generate|set up).*in.*sheet\b',
                r'(?i)\b(build|create|implement|make|generate|set up).*in.*current.*sheet\b'
            ],
            'contextual_reference': [
                r'(?i)\b(as\s+)?(described|mentioned|discussed|outlined|specified)\s+(above|previously|earlier|before)\b',
                r'(?i)\b(the\s+)?(plan|model|structure|format|template)\s+(we|you|I)\s+(discussed|mentioned|described)\b',
                r'(?i)\b(what\s+)?(we|you|I)\s+(talked about|discussed|went over|covered)\b',
                r'(?i)\b(income statement|balance sheet|cash flow|financial model)\s+.*(described|mentioned|outlined)\b'
            ],
            'imperative_with_context': [
                r'(?i)^(now\s+)?(build|create|implement|make|generate|set up)\b',
                r'(?i)^(please\s+)?(build|create|implement|make|generate|set up)\b',
                r'(?i)^(go ahead and\s+)?(build|create|implement|make|generate|set up)\b'
            ]
        }
        
        # Check for reference patterns
        has_reference = False
        reference_type = None
        
        for ref_type, patterns in reference_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message):
                    has_reference = True
                    reference_type = ref_type
                    break
            if has_reference:
                break
        
        # Analyze action intent
        action_keywords = {
            'build': ['build', 'create', 'make', 'construct', 'develop', 'set up', 'establish'],
            'implement': ['implement', 'execute', 'perform', 'carry out', 'do', 'run'],
            'modify': ['modify', 'change', 'update', 'edit', 'adjust', 'alter'],
            'analyze': ['analyze', 'review', 'examine', 'check', 'look at', 'inspect']
        }
        
        detected_action = None
        for action, keywords in action_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                detected_action = action
                break
        
        return {
            'has_context_reference': has_reference,
            'reference_type': reference_type,
            'action_intent': detected_action,
            'message_length': len(message),
            'is_short_command': len(message.split()) <= 5 and has_reference
        }


class Orchestrator:
    """
    Orchestrates the execution flow between different agents.
    Ensures the same model is used for all sub-tasks (planning, execution, evaluation).
    """
    
    def __init__(self, 
                 llm: LLMClient,
                 sheet: Spreadsheet,
                 tool_functions: Dict[str, callable] = None,
                 force_json_mode: bool = False):
        """
        Initialize the orchestrator with the LLM client that will be used for all steps.
        
        Args:
            llm: LLM client that will be used for all agent interactions
            sheet: The spreadsheet object to operate on
            tool_functions: Dictionary of tool functions to use
            force_json_mode: Force JSON mode for models like Groq/Llama that need explicit instructions
        """
        self.llm = llm
        
        # Configure provider-specific options
        provider = getattr(llm, 'provider', '') if hasattr(llm, 'provider') else ''
        
        # Don't apply JSON headers when streaming is used
        # JSON mode is incompatible with streaming in Groq
        
        self.sheet = sheet
        self.tool_functions = tool_functions or {}
        
        # Pre-build agents with the same LLM client
        self.ask_agent = build_ask_agent(llm=self.llm)
        self.analyst_agent = build_analyst_agent(llm=self.llm)
        
        # Bind tool functions if provided
        if self.tool_functions:
            self.ask_agent = self.ask_agent.clone_with_tools(self.tool_functions)
            self.analyst_agent = self.analyst_agent.clone_with_tools(self.tool_functions)
        
        # Store sheet context
        summary = sheet_summary(sheet)
        
        # Backward-compat guard for summary keys
        rows_key = 'rows' if 'rows' in summary else 'n_rows'
        cols_key = 'columns' if 'columns' in summary else 'n_cols'
        
        self.sheet_context = f"[Context] Active sheet '{summary['name']}' has {summary[rows_key]} rows × {summary[cols_key]} cols; Headers: {summary['headers']}."
        
        # Initialize context analyzer
        self.context_analyzer = ContextAnalyzer()
    
    def get_agent(self, mode: str) -> BaseAgent:
        """
        Returns the appropriate agent based on the mode.
        
        Args:
            mode: "ask" or "analyst"
            
        Returns:
            The configured agent
        """
        if mode == "ask":
            return self.ask_agent
        elif mode == "analyst":
            return self.analyst_agent
        else:
            raise ValueError(f"Invalid agent mode: {mode}")
    
    async def run(self, 
                  mode: str, 
                  message: str, 
                  history: Optional[list] = None) -> Dict[str, Any]:
        """
        Run the orchestration process:
        1. Run the appropriate agent (ask/analyst)
        2. For analyst mode, validate the output with the evaluator
        3. Return the result
        
        Args:
            mode: "ask" or "analyst"
            message: User message
            history: Conversation history
            
        Returns:
            Dict with the agent response and any updates
        """
        start_time = time.time()
        request_id = f"orch-{int(start_time*1000)}"
        print(f"[{request_id}] 🎭 Orchestrator.run: mode={mode}, model={self.llm.model}")
        
        # Get the appropriate agent and prepare it with context awareness
        agent = self.get_agent(mode)
        agent = self._prepare_context_aware_agent(agent, mode, message, history)
        
        # For ask mode, limit to 1 iteration to prevent loops
        if mode == "ask":
            # Override the MAX_TOOL_ITERATIONS environment variable for ask mode
            original_max_iterations = os.environ.get("MAX_TOOL_ITERATIONS")
            os.environ["MAX_TOOL_ITERATIONS"] = "1"
            print(f"[{request_id}] 🔧 Limited ask mode to 1 iteration to prevent loops")
        
        try:
            # Apply legacy financial model tool filtering for llama-70b model
            if hasattr(self.llm, 'model') and (
                'llama-3-70b' in self.llm.model or 
                'llama3-70b' in self.llm.model or
                'llama-3.3-70b' in self.llm.model):
                
                financial_keywords = ['financial model', 'statement model', 'fsm', 'financial statement model', 'dcf', '3-statement']
                message_lower = message.lower()
                
                # Only provide financial model tools if explicitly mentioned
                should_include_model_tools = any(keyword in message_lower for keyword in financial_keywords)
                
                if not should_include_model_tools:
                    # Filter out financial model tools from agent's tools
                    financial_model_tools = ["insert_fsm_model", "insert_dcf_model", "insert_fsm_template", "insert_dcf_template"]
                    
                    # Create a new tools list without the financial model tools
                    filtered_tools = []
                    for tool in agent.tools:
                        if tool["name"] not in financial_model_tools:
                            filtered_tools.append(tool)
                    
                    # Create a new agent with filtered tools
                    agent = agent.__class__(
                        llm=agent.llm,
                        fallback_prompt=agent.system_prompt,
                        tools=filtered_tools
                    )
                    print(f"[{request_id}] 🔧 Filtered financial model tools for llama-70b model as they weren't explicitly requested")
            
            # Run the agent
            result = await agent.run(message, history)
            
            # For analyst mode, validate the output
            if mode == "analyst" and "updates" in result and result["updates"]:
                # Validate updates through rule checking
                from chat.validators import validate_updates
                
                try:
                    print(f"[{request_id}] 🔍 Validating {len(result['updates'])} updates")
                    validate_updates(result["updates"])
                    print(f"[{request_id}] ✅ Updates validation passed")
                except ValueError as e:
                    print(f"[{request_id}] ❌ Updates validation failed: {str(e)}")
                    # Replace the result with an error message
                    result["reply"] = f"I couldn't complete your request: {str(e)}"
                    result["updates"] = []  # Clear the updates that failed validation
            
            print(f"[{request_id}] ✅ Orchestrator completed in {time.time() - start_time:.2f}s")
            return result
        
        finally:
            # Restore the original MAX_TOOL_ITERATIONS environment variable
            if mode == "ask":
                if original_max_iterations is None:
                    os.environ.pop("MAX_TOOL_ITERATIONS", None)  # clean delete
                else:
                    os.environ["MAX_TOOL_ITERATIONS"] = original_max_iterations
    
    async def stream_run(self, 
                       mode: str, 
                       message: str, 
                       history: Optional[list] = None) -> AsyncGenerator[ChatStep, None]:
        """
        Streaming version of the orchestration process.
        
        Args:
            mode: "ask" or "analyst"
            message: User message
            history: Conversation history
            
        Yields:
            ChatStep objects from the agent
        """
        start_time = time.time()
        request_id = f"orch-stream-{int(start_time*1000)}"
        debug_orchestrator = os.getenv("DEBUG_STREAMING", "0") == "1"
        
        if debug_orchestrator:
            print(f"[{request_id}] 🎭 Orchestrator.stream_run: mode={mode}, model={self.llm.model}")
            print(f"[{request_id}] 📝 Message: {message[:100]}{'...' if len(message) > 100 else ''}")
            print(f"[{request_id}] 📚 History: {len(history) if history else 0} messages")
            print(f"[{request_id}] 🔍 LLM Provider: {getattr(self.llm, 'name', 'unknown')}")
            print(f"[{request_id}] 🔍 LLM Model: {getattr(self.llm, 'model', 'unknown')}")
            print(f"[{request_id}] 🔍 LLM Supports Tool Calls: {getattr(self.llm, 'supports_tool_calls', 'unknown')}")
        
        # Get the appropriate agent and prepare it with context awareness
        if debug_orchestrator:
            print(f"[{request_id}] 🔍 Getting agent for mode: {mode}")
        agent = self.get_agent(mode)
        if debug_orchestrator:
            print(f"[{request_id}] ✅ Agent obtained: {agent.__class__.__name__}")
            print(f"[{request_id}] 🔧 Agent LLM: {agent.llm.__class__.__name__}")
        
        # Apply context-aware preparation
        agent = self._prepare_context_aware_agent(agent, mode, message, history)
        if debug_orchestrator:
            print(f"[{request_id}] 🧠 Context-aware agent preparation completed")
            print(f"[{request_id}] 🔧 Agent has {len(agent.tools)} tools available:")
            for i, tool in enumerate(agent.tools):
                print(f"[{request_id}]   {i+1}. {tool['name']}")
            print(f"[{request_id}] 📝 System prompt length: {len(agent.system_prompt)} chars")
        
        # For ask mode, limit to 1 iteration to prevent loops
        if mode == "ask":
            # Override the MAX_TOOL_ITERATIONS environment variable for ask mode
            original_max_iterations = os.environ.get("MAX_TOOL_ITERATIONS")
            os.environ["MAX_TOOL_ITERATIONS"] = "1"
            if debug_orchestrator:
                print(f"[{request_id}] 🔧 Limited ask mode to 1 iteration to prevent loops")
        
        try:
            # Apply legacy financial model tool filtering for llama-70b model
            if hasattr(self.llm, 'model') and (
                'llama-3-70b' in self.llm.model or 
                'llama3-70b' in self.llm.model or
                'llama-3.3-70b' in self.llm.model):
                
                financial_keywords = ['financial model', 'statement model', 'fsm', 'financial statement model', 'dcf', '3-statement']
                message_lower = message.lower()
                
                # Only provide financial model tools if explicitly mentioned
                should_include_model_tools = any(keyword in message_lower for keyword in financial_keywords)
                
                if debug_orchestrator:
                    print(f"[{request_id}] 🔍 Llama-70b detected, checking for financial keywords")
                    print(f"[{request_id}] 🔍 Should include model tools: {should_include_model_tools}")
                
                if not should_include_model_tools:
                    # Filter out financial model tools from agent's tools
                    financial_model_tools = ["insert_fsm_model", "insert_dcf_model", "insert_fsm_template", "insert_dcf_template"]
                    
                    # Create a new tools list without the financial model tools
                    filtered_tools = []
                    for tool in agent.tools:
                        if tool["name"] not in financial_model_tools:
                            filtered_tools.append(tool)
                    
                    # Create a new agent with filtered tools
                    agent = agent.__class__(
                        llm=agent.llm,
                        fallback_prompt=agent.system_prompt,
                        tools=filtered_tools
                    )
                    if debug_orchestrator:
                        print(f"[{request_id}] 🔧 Filtered financial model tools for llama-70b model as they weren't explicitly requested")
                        print(f"[{request_id}] 🔧 Tools after filtering: {len(agent.tools)}")
            
            # Stream from the agent - use stream_run instead of run_iter for token-by-token streaming
            if debug_orchestrator:
                print(f"[{request_id}] 🚀 Calling agent.stream_run...")
            agent_stream = agent.stream_run(message, history)
            if debug_orchestrator:
                print(f"[{request_id}] ✅ Agent.stream_run returned: {type(agent_stream)}")
            
            # Verify we got an actual async generator
            if not inspect.isasyncgen(agent_stream):
                if inspect.isawaitable(agent_stream):
                    if debug_orchestrator:
                        print(f"[{request_id}] ⚠️ Agent returned a coroutine instead of an async generator - awaiting once")
                    agent_stream = await agent_stream
                    if debug_orchestrator:
                        print(f"[{request_id}] 🔄 After awaiting: {type(agent_stream)}")
                        if not inspect.isasyncgen(agent_stream):
                            print(f"[{request_id}] ❌ Agent still did not return an async generator after awaiting")
                            raise TypeError("Agent.stream_run did not return an async generator")
                else:
                    print(f"[{request_id}] ❌ Agent did not return an async generator or coroutine")
                    raise TypeError("Agent.stream_run did not return an async generator")
            
            # Now wrap it with the guard
            if debug_orchestrator:
                print(f"[{request_id}] 🛡️ Wrapping stream with guard")
            guarded_stream = wrap_stream_with_guard(agent_stream)
            if debug_orchestrator:
                print(f"[{request_id}] 🔄 Starting to iterate over guarded stream")
            
            step_count = 0
            tool_steps = 0
            content_steps = 0
            error_steps = 0
            
            try:
                async for step in guarded_stream:
                    step_count += 1
                    
                    if debug_orchestrator:
                        step_preview = str(step)[:100] + ('...' if len(str(step)) > 100 else '')
                        print(f"[{request_id}] 📦 Stream step #{step_count}: {type(step)} - {step_preview}")
                    
                    # Track step types for debugging
                    if hasattr(step, 'role'):
                        if step.role == 'tool':
                            tool_steps += 1
                            if debug_orchestrator:
                                tool_name = getattr(step.toolCall, 'name', 'unknown') if hasattr(step, 'toolCall') else 'unknown'
                                print(f"[{request_id}] 🔧 Tool step #{tool_steps}: {tool_name}")
                                if hasattr(step, 'toolResult'):
                                    result_preview = str(step.toolResult)[:100] + ('...' if len(str(step.toolResult)) > 100 else '')
                                    print(f"[{request_id}] 📤 Tool result: {result_preview}")
                        elif step.role == 'assistant':
                            content_steps += 1
                            if hasattr(step, 'content') and step.content:
                                if debug_orchestrator:
                                    content_preview = step.content[:50] + ('...' if len(step.content) > 50 else '')
                                    print(f"[{request_id}] 💬 Content step #{content_steps}: '{content_preview}'")
                    elif isinstance(step, str):
                        content_steps += 1
                        if debug_orchestrator:
                            content_preview = step[:50] + ('...' if len(step) > 50 else '')
                            print(f"[{request_id}] 💬 String content #{content_steps}: '{content_preview}'")
                    
                    # Convert string to ChatStep if needed for consistency
                    if isinstance(step, str):
                        yield ChatStep(role="assistant", content=step)
                    else:
                        yield step
                    
            except Exception as e:
                error_steps += 1
                print(f"[{request_id}] ❌ Error in orchestrator stream: {e}")
                import traceback
                traceback.print_exc()
                # Yield error as content
                yield ChatStep(role="assistant", content=f"Error in processing: {str(e)}")
            
            elapsed = time.time() - start_time
            if debug_orchestrator:
                print(f"[{request_id}] ✅ Orchestrator stream completed in {elapsed:.2f}s")
                print(f"[{request_id}] 📊 Stream statistics:")
                print(f"[{request_id}]   Total steps: {step_count}")
                print(f"[{request_id}]   Tool steps: {tool_steps}")
                print(f"[{request_id}]   Content steps: {content_steps}")
                print(f"[{request_id}]   Error steps: {error_steps}")
        
        finally:
            # Restore the original MAX_TOOL_ITERATIONS environment variable
            if mode == "ask":
                if original_max_iterations is None:
                    os.environ.pop("MAX_TOOL_ITERATIONS", None)  # clean delete
                else:
                    os.environ["MAX_TOOL_ITERATIONS"] = original_max_iterations
    
    def _prepare_context_aware_agent(self, agent: BaseAgent, mode: str, message: str, history: List[Dict[str, Any]] = None) -> BaseAgent:
        """
        Prepare an agent with context-aware instructions based on conversation history.
        This is the core intelligence that mirrors Cursor/Windsurf behavior.
        """
        # Reset system prompt to prevent accumulation
        agent.reset_system_prompt()
        
        # Add sheet context
        agent.add_system_message(self.sheet_context)
        
        if mode == "ask":
            agent.add_system_message("You can both analyze spreadsheet data and provide financial knowledge. When the user asks about data in the current spreadsheet, use your read-only tools first to examine the data. When they ask about financial concepts, modeling techniques, or general knowledge, provide comprehensive explanations directly.")
            return agent
        
        # For analyst mode, perform sophisticated context analysis
        intent_analysis = self.context_analyzer.analyze_user_intent(message, history)
        
        if intent_analysis['has_context_reference']:
            # Extract implementation context from history
            implementation_context = self.context_analyzer.extract_implementation_context(history or [])
            
            if implementation_context:
                # Add sophisticated context-aware instructions
                context_instruction = f"""
CONTEXT-AWARE EXECUTION MODE ACTIVATED:

The user is referencing previous conversation content with intent to {intent_analysis['action_intent'] or 'execute'}.

PREVIOUS CONTEXT TO IMPLEMENT:
{implementation_context}

CRITICAL EXECUTION RULES:
1. DO NOT call apply_updates_and_reply with empty arguments
2. ALWAYS provide specific cell references (e.g., "A1", "B2") and values
3. When building a financial model from the context above:
   - Extract ALL specific cells, labels, and formulas mentioned
   - Start with headers in row 1 (A1, B1, C1, etc.)
   - Build the model cell by cell using set_cell
   - Use apply_updates_and_reply ONLY when you have multiple specific updates ready
4. Example of CORRECT usage:
   apply_updates_and_reply(updates=[
       {{"cell": "A1", "value": "Revenue"}},
       {{"cell": "B1", "value": "2024"}},
       {{"cell": "B2", "value": 1500}}
   ], reply="Built revenue model")
5. NEVER call apply_updates_and_reply with empty updates array or without arguments

EXECUTION INSTRUCTIONS:
1. Analyze the above context to understand EXACTLY what needs to be built/implemented
2. Extract all specific details: labels, formulas, data sources, structure, formatting
3. If it's a financial model/table, identify all required components (inputs, calculations, outputs)
4. Look for any cell references (A1, B2, etc.) and formulas (=SUM, =AVERAGE, etc.) mentioned
5. Implement using proper tool calls with exact cell references and values
6. If formulas are mentioned, use allow_formula=True parameter
7. Build the complete structure step by step, starting with headers/labels
8. Do NOT ask for clarification - proceed with implementation based on the context
9. If multiple options exist, choose the most comprehensive and industry-standard approach

IMMEDIATE ACTION: Build the model described in the context using specific tool calls.
"""
                agent.add_system_message(context_instruction)
                
                print(f"🧠 Context-aware mode activated - implementing from previous context ({len(implementation_context)} chars)")
            else:
                # Fallback for references without clear implementation context
                agent.add_system_message("""
CONTEXT REFERENCE DETECTED: The user is referring to something from previous conversation.
Look at the conversation history to understand what they want you to implement or build.
Extract the most detailed specification or plan from recent messages and execute it.

CRITICAL: When making tool calls:
- NEVER call apply_updates_and_reply with empty arguments
- Always provide specific cell references and values
- Use set_cell for individual updates when uncertain
""")
                print(f"🔗 Context reference detected but no clear implementation context found")
        else:
            # Standard analyst mode instructions
            agent.add_system_message("""
IMPORTANT INSTRUCTION ABOUT FINANCIAL MODELS:
- DO NOT use the insert_fsm_model, insert_dcf_model, insert_fsm_template, or insert_dcf_template tools UNLESS the user EXPLICITLY asks for:
  * a financial statement model (FSM)
  * a discounted cash flow model (DCF)
  * a 3-statement model
  * a financial projection model with multiple statements
- For simple financial tables (single income statement, single balance sheet, etc.), create them directly using set_cell, without using specialized model tools.
- When the user asks for a basic table, NEVER attempt to build a full financial model with multiple statements.
""")
        
        return agent 