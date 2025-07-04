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
        Enhanced for better financial content detection.
        """
        if not history:
            return None
            
        # Enhanced patterns for financial and spreadsheet models
        context_patterns = [
            # Financial models and calculations - more comprehensive
            r'(?i)(wacc|weighted average cost|discount rate|valuation|financial model|income statement)',
            r'(?i)(balance sheet|cash flow|profit.{0,5}loss|p.{0,2}l|financial statement)',
            r'(?i)(dcf|discounted cash flow|fsm|financial statement model|three statement)',
            r'(?i)(revenue|sales|cogs|cost of goods sold|gross profit|operating expense)',
            r'(?i)(ebitda|ebit|net income|free cash flow|terminal value|growth rate)',
            r'(?i)(assumptions|drivers|forecast|projection|budget|plan)',
            
            # Spreadsheet and model structure
            r'(?i)(model|template|table|structure|format|layout|framework)',
            r'(?i)(column|row|cell|formula|calculation|equation|function)',
            r'(?i)(sheet|tab|worksheet|workbook|spreadsheet)',
            
            # Business context
            r'(?i)(company|business|industry|market|competitor|customer)',
            r'(?i)(strategy|plan|analysis|performance|metrics|kpi)',
            
            # Action-oriented language
            r'(?i)(build|create|develop|design|implement|construct|generate)',
            r'(?i)(analyze|calculate|estimate|project|forecast|model)',
            r'(?i)(show|display|provide|give|include|add|insert)',
        ]
        
        relevant_messages = []
        
        # Look at more recent messages (increased from 10 to 15)
        recent_history = history[-15:] if len(history) > 15 else history
        
        for msg in recent_history:
            if msg.get('role') == 'assistant':
                content = msg.get('content', '')
                
                # Enhanced scoring system
                pattern_matches = 0
                content_score = 0
                
                for pattern in context_patterns:
                    matches = re.findall(pattern, content)
                    if matches:
                        pattern_matches += len(matches)
                        # Weight financial terms higher
                        if any(term in pattern.lower() for term in ['financial', 'dcf', 'income', 'cash flow', 'wacc']):
                            content_score += len(matches) * 2
                        else:
                            content_score += len(matches)
                
                # Lower requirements: was >= 3 and > 200, now >= 2 and > 100
                if pattern_matches >= 2 and len(content) > 100:
                    # Calculate quality score
                    quality_score = pattern_matches + (len(content) / 100) + content_score
                    
                    relevant_messages.append({
                        'content': content,
                        'pattern_matches': pattern_matches,
                        'content_score': content_score,
                        'quality_score': quality_score,
                        'length': len(content)
                    })
        
        if not relevant_messages:
            return None
        
        # Sort by quality score and take the best match
        relevant_messages.sort(key=lambda x: x['quality_score'], reverse=True)
        best_match = relevant_messages[0]
        
        # Return the most relevant context with truncation for performance
        context_content = best_match['content']
        if len(context_content) > 1500:  # Increased from 1000
            context_content = context_content[:1500] + "..."
        
        return context_content
    
    @staticmethod
    def analyze_user_intent(message: str, history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze user intent to determine if they're referring to previous context
        and what type of action they want to take.
        """
        message_lower = message.lower().strip()
        
        # Enhanced reference detection patterns for 2025
        reference_patterns = {
            'direct_reference': [
                r'(?i)\b(build|create|implement|make|generate|set up|construct|design)\s+(the\s+)?(above|that|this|it|one)\b',
                r'(?i)\b(do|execute|perform|carry out|run|apply)\s+(the\s+)?(above|that|this|it)\b',
                r'(?i)\b(ok|yes|please|go ahead|proceed)\s+(build|create|implement|make|do)\s+(it|that|this)\b',
                r'(?i)^(ok|yes|please|go ahead|proceed)\s+(build|create|implement|make)\s+(it|that|this|the model|an?\s+model)\b',
                r'(?i)\b(build|create)\s+(an?\s+)?(income statement|financial model|dcf|fsm|model)\b',
            ],
            'financial_requests': [
                r'(?i)\b(income statement|profit.{0,5}loss|p.{0,2}l|financial model|financial statement)\b',
                r'(?i)\b(dcf|discounted cash flow|valuation|financial model)\b',
                r'(?i)\b(fsm|financial statement model|three statement model)\b',
                r'(?i)\b(balance sheet|cash flow statement|statement of cash flows)\b',
                r'(?i)\b(wacc|cost of capital|discount rate|terminal value)\b',
                r'(?i)\b(revenue|cogs|expenses|ebitda|net income|free cash flow)\b',
            ],
            'implementation_requests': [
                r'(?i)\b(build|create|generate|make|implement|set up|construct|design)\b',
                r'(?i)\b(add|insert|put|place|include)\s+(a|an|the)?\s*(table|model|template|structure)\b',
                r'(?i)^(ok|yes|please|sure|alright)\s*,?\s*(build|create|make|do|implement)\b',
                r'(?i)\b(show me|give me|provide|display)\s+(an?\s+)?(example|template|model)\b',
            ],
            'short_confirmations': [
                r'(?i)^(ok|yes|please|sure|alright|go ahead|proceed|do it)\s*\.?$',
                r'(?i)^(build it|make it|create it|do it|implement it)\s*\.?$',
                r'(?i)^(ok build it|yes build it|please build it)\s*(for me)?\s*\.?$',
                r'(?i)^(build|create|make)\s+(it|that|this|the model)\s*(for me)?\s*\.?$',
            ]
        }
        
        # Calculate pattern scores with enhanced detection
        pattern_scores = {}
        for category, patterns in reference_patterns.items():
            score = 0
            for pattern in patterns:
                matches = re.findall(pattern, message)
                if matches:
                    # Give higher scores for financial and implementation requests
                    if category in ['financial_requests', 'implementation_requests']:
                        score += len(matches) * 3  # Higher weight for financial terms
                    elif category == 'short_confirmations':
                        score += len(matches) * 4  # Highest weight for confirmation phrases
                    else:
                        score += len(matches) * 2
            pattern_scores[category] = score
        
        total_score = sum(pattern_scores.values())
        
        # Lower threshold for better responsiveness (was 3, now 2)
        has_context_reference = (
            total_score >= 2 or 
            pattern_scores.get('short_confirmations', 0) >= 2 or
            pattern_scores.get('financial_requests', 0) >= 1 or
            (len(message_lower.split()) <= 6 and pattern_scores.get('implementation_requests', 0) >= 1)
        )
        
        # Enhanced action type detection
        action_type = 'unknown'
        if pattern_scores.get('financial_requests', 0) >= 1:
            action_type = 'financial_modeling'
        elif pattern_scores.get('implementation_requests', 0) >= 2:
            action_type = 'implementation'
        elif pattern_scores.get('short_confirmations', 0) >= 2:
            action_type = 'confirmation'
        elif pattern_scores.get('direct_reference', 0) >= 2:
            action_type = 'reference'
        
        return {
            'has_context_reference': has_context_reference,
            'action_type': action_type,
            'pattern_scores': pattern_scores,
            'total_score': total_score,
            'message_length': len(message.split())
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
        
        # Dynamically choose max iterations based on user intent
        original_max_iterations = os.environ.get("MAX_TOOL_ITERATIONS")
        if mode == "ask":
            os.environ["MAX_TOOL_ITERATIONS"] = "2"  # think → explain
            print(f"[{request_id}] ⚡ Ask mode capped at 2 iterations (think→explain)")
        else:  # analyst
            # Leave MAX_TOOL_ITERATIONS unchanged to allow flexible think→act→explain cycles
            print(f"[{request_id}] 🚀 Analyst mode running without hard iteration cap (think→act→explain groups)")
        
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
            if mode in ("ask", "analyst"):
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
            print(f"[{request_id}] �� LLM Provider: {getattr(self.llm, 'name', 'unknown')}")
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
        
        # Dynamically choose max iterations based on user intent
        original_max_iterations = os.environ.get("MAX_TOOL_ITERATIONS")
        if mode == "ask":
            os.environ["MAX_TOOL_ITERATIONS"] = "2"  # think → explain
            print(f"[{request_id}] ⚡ Ask mode capped at 2 iterations (think→explain)")
        else:  # analyst
            # Leave MAX_TOOL_ITERATIONS unchanged to allow flexible think→act→explain cycles
            print(f"[{request_id}] 🚀 Analyst mode running without hard iteration cap (think→act→explain groups)")
        
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
            if mode in ("ask", "analyst"):
                if original_max_iterations is None:
                    os.environ.pop("MAX_TOOL_ITERATIONS", None)  # clean delete
                else:
                    os.environ["MAX_TOOL_ITERATIONS"] = original_max_iterations
    
    def _prepare_context_aware_agent(self, agent: BaseAgent, mode: str, message: str, history: List[Dict[str, Any]] = None) -> BaseAgent:
        """
        Prepare an agent with context-aware instructions based on conversation history.
        Enhanced to work in both ask and analyst modes for better follow-up handling.
        """
        # Reset system prompt to prevent accumulation
        agent.reset_system_prompt()
        
        # Add sheet context
        agent.add_system_message(self.sheet_context)
        
        # Perform sophisticated context analysis for BOTH ask and analyst modes (enhanced 2025)
        intent_analysis = self.context_analyzer.analyze_user_intent(message, history)
        
        if intent_analysis['has_context_reference']:
            # Extract context from conversation history
            context = self.context_analyzer.extract_implementation_context(history)
            
            if context:
                # Enhanced context-aware prompting
                context_instruction = f"""
CONTEXT-AWARE MODE ACTIVATED 🎯

The user is making a follow-up request that refers to previous conversation context.

PREVIOUS CONTEXT:
{context}

CURRENT REQUEST: "{message}"

ANALYSIS:
- Action Type: {intent_analysis['action_type']}
- Pattern Scores: {intent_analysis['pattern_scores']}
- Message is {'short' if intent_analysis['message_length'] <= 6 else 'detailed'} ({intent_analysis['message_length']} words)

INSTRUCTIONS:
1. **INTERPRET** the current request in the context of the previous conversation
2. **IMPLEMENT** what was discussed or requested in the previous context
3. **BE PROACTIVE** - if they said "build it" or similar, actually build the financial model/analysis
4. **USE TOOLS** - Apply concrete changes to the spreadsheet based on the context
5. **BE SPECIFIC** - Don't just explain, actually create the requested model/analysis

For financial modeling requests:
- Build actual income statements, DCF models, or FSM templates
- Use real formulas and structure
- Apply proper formatting and labels
- Include relevant assumptions and drivers

Remember: The user expects ACTION, not just explanation. IMPLEMENT what was discussed.
"""
                agent.add_system_message(context_instruction)
                
                # For analyst mode, add extra financial modeling context
                if mode == 'analyst':
                    analyst_context = """
ENHANCED ANALYST MODE - FINANCIAL MODELING SPECIALIST

You are a senior financial analyst with expertise in:
- Building comprehensive financial models (DCF, LBO, Comps)
- Creating detailed financial statements (Income Statement, Balance Sheet, Cash Flow)
- Developing assumption-driven models with proper drivers
- Implementing industry best practices for financial modeling

When building models:
1. Start with clear assumptions and drivers
2. Build logical flow from revenues to cash flows
3. Include proper formulas and cell references
4. Add formatting and structure for clarity
5. Provide meaningful insights and analysis

PRIORITY: When asked to build a model, actually create it in the spreadsheet immediately.
"""
                    agent.add_system_message(analyst_context)
        
        return agent 