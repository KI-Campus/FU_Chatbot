"""
Socratic Explain Node - Provides controlled explanation when Socratic method reaches its limit.

Fallback mechanism when hints don't suffice or student explicitly requests explanation.
"""

from langfuse.decorators import observe

from src.llm.state.models import GraphState
from src.llm.objects.LLMs import LLM
from src.llm.prompts.prompt_loader import load_prompt
from src.llm.state.socratic_routing import reset_socratic_state

# Load prompt once at module level
SOCRATIC_EXPLAIN_PROMPT = load_prompt("socratic_explain")


@observe()
def socratic_explain(state: GraphState) -> GraphState:
    """
    Provides controlled explanation when Socratic method reaches its limit.
    
    Purpose:
    - Give clear, structured explanation of the concept
    - Reference student's prior attempts (what was correct/incorrect)
    - Use retrieved course content to ground explanation
    - Offer follow-up practice or move to reflection
    
    Triggers:
    - hint_level == 3 AND contract.allow_explain == True
    - Explicit student request ("Gib mir einfach die Antwort")
    - Fail-policy: Too many attempts without progress
    
    Strategy:
    - Use reranked chunks to provide fact-based explanation
    - Acknowledge student's efforts and partial understanding
    - Provide structured, clear explanation
    - Offer practice opportunity (back to core) or conclude (reflection)
    
    Flow Transitions:
    - → "core": Offer practice with similar problem
    - → "reflection": If student satisfied or goal achieved
    
    Changes:
    - Sets answer with structured explanation
    - Updates student_model (marks topic as explained)
    - Resets hint_level to 0 (for potential practice round)
    - Sets socratic_mode for next step
    
    Args:
        state: Current graph state with reranked chunks, student_model, chat_history
        
    Returns:
        Updated state with explanation and routing decision
    """
    learning_objective = state["learning_objective"]
    chat_history = state["chat_history"]
    student_model = state["student_model"]
    reranked_chunks = state["reranked_chunks"]
    attempt_count = state["attempt_count"]
    model = state["runtime_config"]["model"]
    
    # Prepare context for LLM
    course_materials = "\n\n".join([
        f"[Material {i+1}]\n{chunk.text}"
        for i, chunk in enumerate(reranked_chunks[:3])
    ]) if reranked_chunks else "No specific course materials retrieved."
    
    query_for_llm = f"""Learning Objective: {learning_objective}

Attempt Count: {attempt_count}

Retrieved Course Materials:
{course_materials}"""
    
    # Generate explanation using LLM
    _llm = LLM()
    llm_response = _llm.chat(
        query=query_for_llm,
        chat_history=chat_history,
        model=model,
        system_prompt=SOCRATIC_EXPLAIN_PROMPT
    )
    
    if llm_response.content is None:
        # Fallback if LLM fails
        explanation = (
            f"Lass mich {learning_objective} erklären:\n\n"
            "Leider konnte ich keine detaillierte Erklärung generieren. "
            "Bitte versuche es nochmal oder stelle eine spezifischere Frage."
        )
    else:
        explanation = llm_response.content.strip()
    
    # Add closing text encouraging continuation
    closing_text = "\n\nWir können das Thema gerne nochmal durchgehen oder uns verwandte Konzepte angucken."
    full_response = explanation + closing_text
    
    # Reset all socratic state (explanation given = session complete)
    socratic_reset = reset_socratic_state()
    
    return {
        **state,
        **socratic_reset,  # Reset all socratic fields including socratic_mode=None
        "answer": full_response,
        "citations_markdown": None,  # Clear citations from previous requests
    }