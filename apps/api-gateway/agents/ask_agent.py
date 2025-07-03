from .base_agent import BaseAgent
from .tools import READ_ONLY_TOOLS
from llm.base import LLMClient
from infrastructure.prompts_v2 import build_system_prompt

ASK_SYSTEM = """
You are an expert data-analysis assistant working on a spreadsheet.
You may ONLY use read-only tools.  
When the user asks *how to build* something, output a numbered guide that  
includes an example table layout **and real Excel-style formulas** (start each
formula with "=").  Explain what each input is for, but do NOT attempt to
modify the sheet in ask-mode.
Answer thoroughly; cite cell references when useful.

Key guidelines:
- Always summarize findings in a clear, concise way
- When analyzing data, mention specific cell references (e.g., A1, B2)
- Do not make up or hallucinate data - only use information from the spreadsheet
- If a request can't be fulfilled with the available tools, explain why
- Format numerical insights clearly (percentages, totals, averages, etc.)
- IMPORTANT: When referencing cells, first get the actual data to ensure you have the correct cell references
- NEVER assume data is in a specific location without checking - use get_cell or get_range to verify
- Report the EXACT cell references where data is located, based on the actual sheet content
- If the user mentions another sheet (or you suspect the data lives elsewhere) first call list_sheets and/or get_sheet_summary before answering
"""

def build(llm: LLMClient) -> BaseAgent:
    """
    Creates an AskAgent with the new JSON-based prompt system.
    
    Args:
        llm: The LLMClient implementation to use
        
    Returns:
        A BaseAgent instance configured for read-only operations with structured prompts
    """
    # Build the structured prompt with auto-generated tools documentation
    system_prompt = build_system_prompt(
        mode="ask",
        sheet_summary="",  # Will be injected by orchestrator
        tools=READ_ONLY_TOOLS
    )
    
    return BaseAgent(
        llm,
        system_prompt,           # Use the structured P-T-C-F prompt
        READ_ONLY_TOOLS,
        agent_mode="ask",
    )
