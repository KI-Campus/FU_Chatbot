"""
Socratic intent routing - checks if user wants to continue or exit socratic mode.
"""
from typing import List, Dict, Any

from llama_index.core.llms import ChatMessage
from langfuse.decorators import observe

from src.llm.objects.LLMs import LLM, Models
from src.llm.prompts.prompt_loader import load_prompt

# Load prompt once at module level
ROUTER_SOCRATIC_PROMPT = load_prompt("router_socratic_prompt")


def reset_socratic_state() -> Dict[str, Any]:
    """
    Reset all socratic-specific state fields to initial/clean state.
    
    Called when socratic mode ends (reflection, explain, or contextualizer exit).
    Ensures clean slate for next socratic or non-socratic interaction.
    
    Returns:
        Dict with all socratic fields reset to None/0/False
    """
    return {
        "socratic_mode": None,
        "student_model": {
            "mastery": "unknown",
            "misconceptions": [],
            "affect": "neutral",
            "prior_knowledge": None,
        },
        "learning_objective": None,
        "attempt_count": 0,
        "hint_level": 0,
        "stuckness_score": 0.0,
        "goal_achieved": False,
        "socratic_contract": None,
    }


@observe()
def should_continue_socratic(user_query: str, chat_history: List[ChatMessage], model: Models) -> bool:
    """
    Checks if user wants to continue socratic dialogue or exit.
    
    Uses LLM with router_socratic_prompt.txt to determine intent.
    Expects LLM to return: "true" or "false"
    
    Args:
        user_query: Current user query
        model: LLM model to use
        
    Returns:
        True if continue socratic, False if user wants to exit
    """
    # Initialize LLM instance
    _llm = LLM()
    
    # Call LLM to determine intent
    response = _llm.chat(
        query=user_query,
        chat_history=chat_history,
        model=model,
        system_prompt=ROUTER_SOCRATIC_PROMPT
    )
    
    if response.content is None:
        raise ValueError(
            f"Socratic router response is None. Please check the LLM implementation. Response: {response}"
        )
    
    # Parse boolean response
    response_clean = response.content.lower().strip()
    
    # Expected: "true" or "false"
    if response_clean == "true":
        return True
    elif response_clean == "false":
        return False
    else:
        # Fallback parsing for partial matches
        if "true" in response_clean:
            return True
        elif "false" in response_clean:
            return False
        else:
            # Default: Continue (be conservative, don't exit unless clear signal)
            return True
