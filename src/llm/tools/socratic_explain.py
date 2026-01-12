"""
Socratic Explain Node - Provides controlled explanation when Socratic method reaches its limit.

Fallback mechanism when hints don't suffice or student explicitly requests explanation.
"""

from langfuse.decorators import observe

from src.llm.state.models import GraphState
from src.llm.objects.LLMs import LLM
from src.llm.prompts.prompt_loader import load_prompt

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
    learning_objective = state.get("learning_objective", "")
    chat_history = state.get("chat_history", [])
    student_model = state.get("student_model", {})
    reranked_chunks = state.get("reranked", [])
    attempt_count = state.get("attempt_count", 0)
    model = state.get("model", "gpt-4o-mini")
    
    # Prepare context for LLM
    course_materials = "\n\n".join([
        f"[Material {i+1}]\n{chunk.page_content}"
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
        full_response = (
            f"Lass mich {learning_objective} erklären:\n\n"
            "Leider konnte ich keine detaillierte Erklärung generieren. "
            "Bitte versuche es nochmal oder stelle eine spezifischere Frage."
        )
    else:
        full_response = llm_response.content.strip()
    
    # Update student model to mark concept as explained
    updated_student_model = {
        **student_model,
        "mastery": "explained",  # Concept was explained, not self-discovered
        "learning_path": "socratic_with_explanation",  # Tracked for analytics
    }
    
    # Reset hint level and stuckness (explanation resolves both)
    new_hint_level = 0
    new_stuckness = 0.0
    
    # After explanation, move to reflection to consolidate learning
    # This is the natural endpoint of the explain path
    next_mode = "reflection"
    
    # Mark goal as achieved (explanation given)
    goal_achieved = True
    
    return {
        **state,
        "student_model": updated_student_model,
        "socratic_mode": next_mode,
        "hint_level": new_hint_level,
        "stuckness_score": new_stuckness,
        "goal_achieved": goal_achieved,
        "answer": full_response,
    }
