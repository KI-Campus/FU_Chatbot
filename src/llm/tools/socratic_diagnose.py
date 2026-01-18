"""
Socratic Diagnose Node - Assesses student's current understanding and identifies learning objective.

Second step in socratic workflow: Diagnostic assessment to establish baseline.
"""

from langfuse.decorators import observe

from src.llm.state.models import GraphState
from src.llm.objects.LLMs import LLM
from src.llm.prompts.prompt_loader import load_prompt

# Load prompt once at module level
SOCRATIC_DIAGNOSE_PROMPT = load_prompt("socratic_diagnose")

# Initialize LLM instance at module level
_llm = LLM()


@observe()
def socratic_diagnose(state: GraphState) -> dict:
    """
    Diagnoses student's current understanding and identifies learning objective.
    
    Purpose:
    - Extract learning objective from user query
    - Assess student's baseline knowledge
    - Initialize student model for tracking progress
    - Ask diagnostic question to gather more context
    
    Flow:
    - Always transitions to "core" next
    
    Changes:
    - Sets learning_objective (extracted from query)
    - Initializes student_model with baseline assessment
    - Sets socratic_mode = "core" for next step
    - Sets answer with diagnostic question
    
    Args:
        state: Current graph state with user_query and chat_history
        
    Returns:
        Updated state with learning objective and student model
    """
    # Get necessary data from state
    user_query = state["user_query"]
    chat_history = state.get("chat_history", [])
    model = state["runtime_config"]["model"]
    
    # LLM-Call to extract learning objective and diagnostic question
    response = _llm.chat(
        query=user_query,
        chat_history=chat_history,
        model=model,
        system_prompt=SOCRATIC_DIAGNOSE_PROMPT
    )
    
    # Parse response
    learning_objective = ""
    diagnostic_question = ""
    
    if response.content:
        lines = response.content.strip().split('\n')
        for line in lines:
            if line.startswith('LEARNING_OBJECTIVE:'):
                learning_objective = line.split(':', 1)[1].strip()
            elif line.startswith('DIAGNOSTIC_QUESTION:'):
                diagnostic_question = line.split(':', 1)[1].strip()
    
    # Fallback if parsing fails
    if not learning_objective:
        learning_objective = f"Verstehe: {user_query}"
    if not diagnostic_question:
        diagnostic_question = "Was weißt du bereits über dieses Thema?"
    
    # Initialize student model with unknown baseline
    student_model = {
        "mastery": "unknown",
        "misconceptions": [],
        "affect": "neutral",
        "prior_knowledge": None,
    }
    
    return {
        "learning_objective": learning_objective,
        "student_model": student_model,
        "socratic_mode": "core",
        "answer": diagnostic_question
    }
