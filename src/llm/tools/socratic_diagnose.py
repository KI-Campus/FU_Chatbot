"""
Socratic Diagnose Node - Assesses student's current understanding and identifies learning objective.

Second step in socratic workflow: Diagnostic assessment to establish baseline.
"""

from langfuse.decorators import observe

from src.llm.state.models import GraphState, build_active_socratic_agent_state
from src.llm.objects.LLMs import LLM
from src.llm.prompts.prompt_loader import load_prompt
from src.llm.streaming import StreamPhaseContext

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
    - Fills diagnosis_artifact in socratic_agent state
    - Sets agent phase to core
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
    with StreamPhaseContext("final"):
        response = _llm.chat(
            query=user_query,
            chat_history=chat_history,
            model=model,
            system_prompt=SOCRATIC_DIAGNOSE_PROMPT
        )
    
    # Parse response
    diagnosis_ready = False
    learning_objective = ""
    diagnostic_question = ""
    
    if response.content:
        lines = response.content.strip().split('\n')
        for line in lines:
            if line.startswith('DIAGNOSIS_READY:'):
                diagnosis_ready = line.split(':', 1)[1].strip().upper() == "YES"
            elif line.startswith('LEARNING_OBJECTIVE:'):
                learning_objective = line.split(':', 1)[1].strip()
            elif line.startswith('DIAGNOSTIC_QUESTION:'):
                diagnostic_question = line.split(':', 1)[1].strip()
    
    # Fallback if parsing fails
    if not diagnostic_question:
        diagnostic_question = "Welches konkrete Thema möchtest du im Lernmodus verstehen?"

    # Require explicit diagnosis readiness and non-empty objective before entering core.
    if not learning_objective or learning_objective.upper() == "NONE":
        diagnosis_ready = False
    
    existing_agent = state.get("socratic_agent") or {}
    agent = {
        **build_active_socratic_agent_state(),
        **existing_agent,
        "active": True,
        "phase": "core" if diagnosis_ready else "diagnosis",
        "diagnosis_artifact": f"diagnosis_completed:{learning_objective}" if diagnosis_ready else None,
        "learning_objective": learning_objective if diagnosis_ready else None,
        "last_executed_tool": "diagnosis",
        "planned_tool": None,
    }
    
    return {
        "socratic_agent": agent,
        "answer": diagnostic_question,
        "citations_markdown": None,
    }
