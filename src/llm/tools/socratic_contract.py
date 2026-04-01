"""
Socratic Contract Node - Establishes learning agreement.

First step in socratic workflow: Clarifies expectations and sets up the learning contract.
"""

from langfuse.decorators import observe

from src.llm.objects.LLMs import LLM
from src.llm.prompts.prompt_loader import load_prompt
from src.llm.state.models import GraphState, build_active_socratic_agent_state
from src.llm.streaming import StreamPhaseContext


SOCRATIC_CONTRACT_PROMPT = load_prompt("socratic_contract")
_llm = LLM()


@observe()
def socratic_contract(state: GraphState) -> dict:
    """
    Establishes a learning contract with the student.
    
    Purpose:
    - Inform student about Socratic approach (questions instead of direct answers)
    - Set expectations for the learning interaction
    - Initialize socratic-specific state fields
    
    Flow:
    - Always transitions to "diagnose" next
    
    Changes:
    - Fills contract_artifact in socratic_agent state
    - Resets core counters
    - Sets agent phase to diagnosis
    - Sets answer with welcome message
    
    Args:
        state: Current graph state with user_query
        
    Returns:
        Updated state with contract and initial socratic fields
    """
    user_query = state["user_query"]
    chat_history = state.get("chat_history", [])
    model = state["runtime_config"]["model"]

    with StreamPhaseContext("final"):
        response = _llm.chat(
            query=user_query,
            chat_history=chat_history,
            model=model,
            system_prompt=SOCRATIC_CONTRACT_PROMPT,
        )

    contract_ready = False
    contract_response = "Ich unterstütze dich gern im Lernmodus. Welches konkrete Thema möchtest du verstehen?"

    if response.content:
        for line in response.content.strip().split("\n"):
            if line.startswith("CONTRACT_READY:"):
                contract_ready = line.split(":", 1)[1].strip().upper() == "YES"
            elif line.startswith("CONTRACT_RESPONSE:"):
                parsed_response = line.split(":", 1)[1].strip()
                if parsed_response:
                    contract_response = parsed_response

    existing_agent = state.get("socratic_agent") or {}
    agent = {
        **build_active_socratic_agent_state(),
        **existing_agent,
        "active": True,
        "phase": "diagnosis" if contract_ready else "contract",
        "contract_artifact": "contract_completed" if contract_ready else None,
        "attempt_count": 0,
        "number_given_hints": 0,
        "feedback_required": False,
        "feedback_done": False,
        "last_core_tool": None,
        "last_executed_tool": "contract",
        "planned_tool": None,
        "pending_feedback_prefix": None,
    }
    
    return {
        "socratic_agent": agent,
        "answer": contract_response,
        "citations_markdown": None,  # Clear citations from previous requests
    }