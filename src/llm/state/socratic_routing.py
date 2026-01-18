from typing import Dict, Tuple, Any, List

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
                           model: Models) -> Tuple[bool, bool, bool]:
    """
    Evaluate user response to determine if they need hint, achieved goal, or want explanation.
    
    Uses LLM to assess:
    1. Whether the student explicitly requests explanation (allow_explain)
    2. Whether the student needs a hint (allow_hint)
    3. Whether the learning objective has been achieved (goal_achieved)
    
    Args:
        user_query: Student's current response
        chat_history: Previous conversation messages
        learning_objective: The learning goal for this session
        attempt_count: Number of attempts so far
        model: Which LLM model to use
        
    Returns:
        Tuple[allow_explain, allow_hint, goal_achieved]:
        - allow_explain: True if student explicitly requests direct explanation
        - allow_hint: True if student appears stuck/frustrated and needs hint
        - goal_achieved: True if student demonstrates understanding of objective
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
        return False, False, False
    
    # Parse LLM response
    lines = response.content.strip().split('\n')
    allow_explain = False
    allow_hint = False
    goal_achieved = False
    
    for line in lines:
        line = line.strip()
        if line.startswith('ALLOW_EXPLAIN:'):
            value = line.split(':', 1)[1].strip().lower()
            allow_explain = value == 'true'
        elif line.startswith('ALLOW_HINT:'):
            value = line.split(':', 1)[1].strip().lower()
            allow_hint = value == 'true'
        elif line.startswith('GOAL_ACHIEVED:'):
            value = line.split(':', 1)[1].strip().lower()
            goal_achieved = value == 'true'
    
    return allow_explain, allow_hint, goal_achieved

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
        "goal_achieved": False,
        "answer": response
    }