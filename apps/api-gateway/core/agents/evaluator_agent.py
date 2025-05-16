from typing import Dict, Any, Optional
import json

from llm.base import LLMClient
from .base_agent import BaseAgent
from .tools import READ_ONLY_TOOLS

EVALUATOR_SYSTEM = """
You are an evaluator agent that judges if a spreadsheet analyst's proposed operations
comply with system policies and rules. Your job is to detect potential issues before
they are applied to the sheet.

You will be given:
1. The user's original request
2. The analyst's proposed updates and response
3. The current sheet state

Evaluate based on these criteria:
- Do the proposed changes stay within the allowed range (max cell: J30)?
- Does the operation use formulas only when explicitly requested?
- Are the updates reasonably related to what the user asked for?
- Does the response clearly explain what changes were made?
- Does the response avoid making false claims?

Rate the proposed operation on a scale of 0.0 to 1.0, where:
- 1.0: Fully compliant, well-explained, and appropriate
- 0.5: Minor issues but generally acceptable
- 0.0: Major violations or inappropriate changes

Return a JSON with your evaluation:
{
  "score": 0.0-1.0,
  "reasoning": "Explanation of your judgment",
  "issues": ["List of specific issues found"]
}

Be strict and thorough in your evaluation.
"""

def build(llm: LLMClient) -> BaseAgent:
    """
    Creates an EvaluatorAgent with the given LLM client.
    This agent evaluates proposed changes from an analyst agent.
    
    Args:
        llm: The LLMClient implementation to use
        
    Returns:
        A BaseAgent instance configured for evaluation
    """
    return BaseAgent(
        llm,
        EVALUATOR_SYSTEM,
        READ_ONLY_TOOLS,  # Only read-only tools since the evaluator doesn't modify
        agent_mode=None,  # No specific DB prompt for this
    )

class EvaluatorAgent:
    """Wrapper for evaluating analyst outputs"""
    
    def __init__(self, llm: LLMClient):
        """
        Initialize the evaluator agent.
        
        Args:
            llm: LLM client to use for evaluation
        """
        self.agent = build(llm)
    
    async def evaluate(self, 
                       user_query: str, 
                       analyst_response: Dict[str, Any], 
                       sheet_summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate an analyst agent's response against policy criteria.
        
        Args:
            user_query: Original user question
            analyst_response: The response from the analyst agent
            sheet_summary: Summary of the current sheet state
            
        Returns:
            Dict with evaluation results including score and reasoning
        """
        # Construct the evaluation prompt
        prompt = f"""
Please evaluate this analyst response:

USER QUERY:
{user_query}

ANALYST RESPONSE:
{analyst_response.get('reply', 'No reply provided')}

PROPOSED UPDATES:
{json.dumps(analyst_response.get('updates', []), indent=2)}

SHEET SUMMARY:
{json.dumps(sheet_summary, indent=2)}

Evaluate if this response complies with our guidelines and return your evaluation as JSON.
"""
        
        # Run the evaluation
        result = await self.agent.run(prompt)
        
        # Try to extract the evaluation JSON
        try:
            if isinstance(result.get('reply'), str):
                # Look for JSON in the reply
                import re
                json_match = re.search(r'\{[\s\S]*\}', result.get('reply', '{}'))
                if json_match:
                    eval_json = json.loads(json_match.group(0))
                    return eval_json
            
            # If we can't extract JSON, return a default evaluation
            return {
                "score": 0.5,  # Middle ground if we can't parse
                "reasoning": "Could not properly parse evaluation",
                "issues": ["Evaluation format error"]
            }
        except Exception as e:
            print(f"Error parsing evaluator response: {e}")
            return {
                "score": 0.5,
                "reasoning": f"Error during evaluation: {str(e)}",
                "issues": ["Evaluation processing error"]
            } 