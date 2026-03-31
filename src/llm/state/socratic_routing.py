from typing import Dict, Any, List

from src.api.models.serializable_chat_message import SerializableChatMessage
from src.llm.objects.LLMs import LLM, Models
from src.llm.prompts.prompt_loader import load_prompt

# Initiate LLm instance
llm = LLM()
# Load prompt once at module level
ROUTER_SOCRATIC_PROMPT = load_prompt("socratic_stuckness_goal_achievement")

def evaluate_user_response(user_query: str,
                           chat_history: List[SerializableChatMessage],
                           learning_objective: str,
                           attempt_count: int,
                           model: Models) -> str:
    """
    Evaluate user response to determine which mode the Socratic dialogue should take.
    
    Uses LLM to assess the student's state and return one of four modes:
    - EXPLAIN: Student explicitly requests direct explanation
    - HINT: Student is stuck and needs guidance
    - REFLECT: Student has achieved the learning objective
    - CONTINUE: Student is progressing well, continue Socratic dialogue
    
    Args:
        user_query: Student's current response
        chat_history: Previous conversation messages
        learning_objective: The learning goal for this session
        attempt_count: Number of attempts so far
        model: Which LLM model to use
        
    Returns:
        str: One of "EXPLAIN", "HINT", "REFLECT", or "CONTINUE"
    """
    
    # Build evaluation query
    evaluation_query = f"""Learning Objective: {learning_objective}

Attempt Count: {attempt_count}

Student's Current Response: {user_query}"""
    
    # Call LLM for evaluation
    response = llm.chat(
        query=evaluation_query,
        chat_history=chat_history,
        model=model,
        system_prompt=ROUTER_SOCRATIC_PROMPT
    )
    
    if response.content is None:
        # Fallback: assume student is progressing
        return "CONTINUE"
    
    # Parse LLM response
    content = response.content.strip()
    
    # Look for MODE: prefix
    if "MODE:" in content:
        mode = content.split("MODE:")[1].strip().split()[0].upper()
        if mode in ["EXPLAIN", "HINT", "REFLECT", "CONTINUE"]:
            return mode
    
    # Fallback if parsing fails
    return "CONTINUE"

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
        "socratic_contract": None,
        "learning_objective": None,
        "attempt_count": 0,
        "number_given_hints": 0,
        "goal_achieved": False
    }

def answer_and_reset_socratic_state(next_mode: str, response: str) -> Dict[str, Any]:
    """
    Reset all socratic-specific state fields to initial/clean state.
    
    Called when socratic mode ends (reflection, explain, or contextualizer exit).
    Ensures clean slate for next socratic or non-socratic interaction.
    
    Returns:
        Dict with all socratic fields reset to None/0/False
    """
    return {
        "socratic_mode": next_mode,
        "socratic_contract": None,
        "learning_objective": None,
        "attempt_count": 0,
        "number_given_hints": 0,
        "goal_achieved": False,
        "answer": response
    }