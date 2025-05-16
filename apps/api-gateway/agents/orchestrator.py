from typing import Optional, Dict, Any, AsyncGenerator
import time

from llm.base import LLMClient
from llm.factory import get_client
from .analyst_agent import build as build_analyst_agent
from .ask_agent import build as build_ask_agent
from .base_agent import BaseAgent, ChatStep
from spreadsheet_engine.model import Spreadsheet
from spreadsheet_engine.summary import sheet_summary


class Orchestrator:
    """
    Orchestrates the execution flow between different agents.
    Ensures the same model is used for all sub-tasks (planning, execution, evaluation).
    """
    
    def __init__(self, 
                 llm: LLMClient,
                 sheet: Spreadsheet,
                 tool_functions: Dict[str, callable] = None):
        """
        Initialize the orchestrator with the LLM client that will be used for all steps.
        
        Args:
            llm: LLM client that will be used for all agent interactions
            sheet: The spreadsheet object to operate on
            tool_functions: Dictionary of tool functions to use
        """
        self.llm = llm
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
        
        # Add sheet context if not already there
        agent.add_system_message(self.sheet_context)
        
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
        print(f"[{request_id}] 🎭 Orchestrator.stream_run: mode={mode}, model={self.llm.model}")
        
        # Get the appropriate agent
        agent = self.get_agent(mode)
        
        # Add sheet context if not already there
        agent.add_system_message(self.sheet_context)
        
        # Stream from the agent
        async for step in agent.run_iter(message, history):
            # For analyst mode, we could add validation here if needed
            # For now, just pass through the ChatStep
            yield step
        
        print(f"[{request_id}] ✅ Orchestrator stream completed in {time.time() - start_time:.2f}s") 