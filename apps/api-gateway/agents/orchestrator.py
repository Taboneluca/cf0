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
    Analyzes conversation history to extract actionable context for agent instructions.
    This mimics how tools like Cursor and Windsurf understand user intent across modes.
    """
    
    @staticmethod
    def extract_actionable_context(message: str, history: Optional[list] = None) -> Optional[str]:
        """
        Analyzes the user message and conversation history to extract actionable context.
        Returns detailed instructions for what the agent should build/implement.
        """
        if not history:
            return None
            
        # Detect context reference patterns (covers thousands of variations)
        reference_patterns = [
            r'\b(build|create|implement|make|generate|add|set up|construct)\s+(the\s+)?(above|that|this|it|those)\b',
            r'\b(do|apply|execute|perform)\s+(the\s+)?(above|that|this|it|those)\b',
            r'\b(use|take|follow|adopt)\s+(the\s+)?(above|that|this|it|those)\b',
            r'\b(based\s+on|according\s+to|using|with)\s+(the\s+)?(above|that|this|it|those)\b',
            r'\bwhat\s+i\s+(mentioned|said|described|outlined|specified|asked\s+for)\b',
            r'\b(from\s+)?(the\s+)?(previous|earlier|last|recent)\s+(message|conversation|discussion|request)\b',
            r'\b(as\s+)?(mentioned|described|outlined|specified|discussed)\s+(before|earlier|above|previously)\b'
        ]
        
        message_lower = message.lower()
        has_reference = any(re.search(pattern, message_lower, re.IGNORECASE) for pattern in reference_patterns)
        
        if not has_reference:
            return None
            
        # Extract the most recent and detailed specification from history
        context_content = ContextAnalyzer._extract_specification_from_history(history)
        
        if context_content:
            return f"""
CONTEXT-AWARE EXECUTION: The user is referencing previous conversation content.

EXTRACTED SPECIFICATION:
{context_content}

INSTRUCTIONS:
1. Analyze the extracted specification carefully
2. Identify all components, requirements, and details mentioned
3. Implement the specification completely using appropriate tools
4. If building a model/table, include all fields, formulas, and structure mentioned
5. Maintain the exact terminology and approach described in the specification
6. If any part is unclear, implement the most logical interpretation based on context

Your task is to execute this specification, not to ask clarifying questions about it.
"""
        
        return None
    
    @staticmethod
    def _extract_specification_from_history(history: list) -> Optional[str]:
        """
        Extracts the most detailed specification or description from conversation history.
        Prioritizes recent, detailed content with actionable information.
        """
        if not history:
            return None
            
        # Look for detailed specifications in reverse chronological order
        specifications = []
        
        for message in reversed(history):
            if message.get("role") != "user":
                continue
                
            content = message.get("content", "")
            if not content:
                continue
                
            # Score content based on detail and actionability
            score = ContextAnalyzer._score_content_detail(content)
            
            if score > 50:  # Threshold for detailed content
                specifications.append({
                    "content": content,
                    "score": score
                })
        
        # Return the highest scoring specification
        if specifications:
            best_spec = max(specifications, key=lambda x: x["score"])
            return best_spec["content"]
            
        return None
    
    @staticmethod
    def _score_content_detail(content: str) -> int:
        """
        Scores content based on how detailed and actionable it is.
        Higher scores indicate more detailed specifications.
        """
        score = 0
        content_lower = content.lower()
        
        # Length indicates detail level
        score += min(len(content) // 10, 30)
        
        # Financial/business model indicators
        financial_terms = [
            'wacc', 'dcf', 'financial model', 'valuation', 'cash flow', 'income statement',
            'balance sheet', 'cost of capital', 'risk free rate', 'beta', 'market risk premium',
            'debt', 'equity', 'npv', 'irr', 'revenue', 'expenses', 'formula', 'calculation'
        ]
        score += sum(5 for term in financial_terms if term in content_lower)
        
        # Structure indicators
        structure_terms = [
            'steps', 'detailed', 'model', 'table', 'columns', 'rows', 'fields',
            'inputs', 'outputs', 'source', 'data', 'labels', 'build', 'create'
        ]
        score += sum(3 for term in structure_terms if term in content_lower)
        
        # Specificity indicators
        specific_terms = [
            'cell', 'a1', 'b1', 'formula', 'rate', 'percentage', 'value',
            'industry standard', 'calculate', 'compute'
        ]
        score += sum(2 for term in specific_terms if term in content_lower)
        
        # Numbered lists or bullet points indicate structured specifications
        if re.search(r'\d+\.\s+', content) or re.search(r'[-*]\s+', content):
            score += 15
            
        # Multiple sentences indicate detailed explanation
        sentence_count = len(re.findall(r'[.!?]+', content))
        score += min(sentence_count * 2, 20)
        
        return score


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
        
        # Get the appropriate agent
        agent = self.get_agent(mode)
        
        # Reset system prompt to prevent accumulation from previous mode switches
        agent.reset_system_prompt()
        
        # Add sheet context if not already there
        agent.add_system_message(self.sheet_context)
        
        # For ask mode, add explicit instruction to not generate any financial templates
        if mode == "ask":
            agent.add_system_message("You can both analyze spreadsheet data and provide financial knowledge. When the user asks about data in the current spreadsheet, use your read-only tools first to examine the data. When they ask about financial concepts, modeling techniques, or general knowledge, provide comprehensive explanations directly.")
        
        # For analyst mode, apply context-aware execution
        elif mode == "analyst":
            # Use the robust context analyzer to extract actionable context
            context_instructions = ContextAnalyzer.extract_actionable_context(message, history)
            
            if context_instructions:
                agent.add_system_message(context_instructions)
                print(f"[{request_id}] 🧠 Applied context-aware instructions for analyst mode")
            
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
        
        # For llama-70b model specifically, filter out complex financial model tools
        # unless they're explicitly requested in the user message
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
    
    async def stream_run(self, 
                       mode: str, 
                       message: str, 
                       history: Optional[list] = None) -> AsyncGenerator[ChatStep, None]:
        """
        Stream the orchestration process - similar to run() but yields ChatStep objects.
        
        Args:
            mode: "ask" or "analyst"
            message: User message
            history: Conversation history
            
        Yields:
            ChatStep objects from the agent execution
        """
        start_time = time.time()
        request_id = f"orch-stream-{int(start_time*1000)}"
        print(f"[{request_id}] 🎭 Orchestrator.stream_run: mode={mode}, model={self.llm.model}")
        
        # Get the appropriate agent
        agent = self.get_agent(mode)
        
        # Reset system prompt to prevent accumulation from previous mode switches
        agent.reset_system_prompt()
        
        # Add sheet context
        agent.add_system_message(self.sheet_context)
        
        # Mode-specific configuration
        if mode == "ask":
            agent.add_system_message("You can both analyze spreadsheet data and provide financial knowledge. When the user asks about data in the current spreadsheet, use your read-only tools first to examine the data. When they ask about financial concepts, modeling techniques, or general knowledge, provide comprehensive explanations directly.")
        
        elif mode == "analyst":
            # Apply context-aware execution for analyst mode
            context_instructions = ContextAnalyzer.extract_actionable_context(message, history)
            
            if context_instructions:
                agent.add_system_message(context_instructions)
                print(f"[{request_id}] 🧠 Applied context-aware instructions for streaming analyst mode")
            
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
        
        # Apply llama-70b filtering if needed
        if hasattr(self.llm, 'model') and (
            'llama-3-70b' in self.llm.model or 
            'llama3-70b' in self.llm.model or
            'llama-3.3-70b' in self.llm.model):
            
            financial_keywords = ['financial model', 'statement model', 'fsm', 'financial statement model', 'dcf', '3-statement']
            message_lower = message.lower()
            
            should_include_model_tools = any(keyword in message_lower for keyword in financial_keywords)
            
            if not should_include_model_tools:
                financial_model_tools = ["insert_fsm_model", "insert_dcf_model", "insert_fsm_template", "insert_dcf_template"]
                
                filtered_tools = []
                for tool in agent.tools:
                    if tool["name"] not in financial_model_tools:
                        filtered_tools.append(tool)
                
                agent = agent.__class__(
                    llm=agent.llm,
                    fallback_prompt=agent.system_prompt,
                    tools=filtered_tools
                )
                print(f"[{request_id}] 🔧 Filtered financial model tools for llama-70b streaming")
        
        # Stream the agent execution
        async for step in agent.stream_run(message, history):
            yield step
        
        print(f"[{request_id}] ✅ Orchestrator streaming completed in {time.time() - start_time:.2f}s") 