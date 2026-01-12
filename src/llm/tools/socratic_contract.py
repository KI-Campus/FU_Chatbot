"""
Socratic Contract Node - Establishes learning agreement.

First step in socratic workflow: Clarifies expectations and sets up the learning contract.
"""

from langfuse.decorators import observe

from src.llm.state.models import GraphState


@observe()
def socratic_contract(state: GraphState) -> GraphState:
    """
    Establishes a learning contract with the student.
    
    Purpose:
    - Inform student about Socratic approach (questions instead of direct answers)
    - Set expectations for the learning interaction
    - Initialize socratic-specific state fields
    
    Flow:
    - Always transitions to "diagnose" next
    
    Changes:
    - Sets socratic_contract with default permissions
    - Initializes hint_level, attempt_count, stuckness_score, goal_achieved
    - Sets socratic_mode = "diagnose" for next step
    - Sets answer with welcome message
    
    Args:
        state: Current graph state with user_query
        
    Returns:
        Updated state with contract and initial socratic fields
    """
    # Default contract: Socratic method enabled, no direct answers upfront
    contract = {
        "allow_explain": False,  # Only after hint_level==3 or explicit user request
        "allow_direct_answer": False,  # Socratic method means no direct solutions
    }
    
    # Welcome message explaining the Socratic approach
    welcome_message = (
        "🎓 Ich sehe, du möchtest etwas lernen!\n\n"
        "Ich werde dich durch gezielte Fragen dabei unterstützen, "
        "die Antwort selbst zu erarbeiten. Das hilft dir, das Thema wirklich zu verstehen.\n"
        "Bist du bereit, gemeinsam zu arbeiten? "
        "(Du kannst jederzeit sagen \"Gib mir einfach die Antwort\", falls du eine direkte Erklärung bevorzugst.)"
    )
    
    return {
        **state,
        "socratic_contract": contract,
        "socratic_mode": "diagnose",
        "hint_level": 0,
        "attempt_count": 0,
        "stuckness_score": 0.0,
        "goal_achieved": False,
        "answer": welcome_message,
    }
