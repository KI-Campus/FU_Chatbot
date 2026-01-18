from typing import Dict, Any

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
        "socratic_contract": None,
        "learning_objective": None,
        "student_model": {
            "mastery": "unknown",
            "misconceptions": [],
            "affect": "neutral",
            "prior_knowledge": None,
        },
        "hint_level": 0,
        "attempt_count": 0,
        "stuckness_score": 0.0,
        "goal_achieved": False
    }