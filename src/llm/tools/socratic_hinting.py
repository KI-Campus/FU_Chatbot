"""
Socratic Hinting Node - Provides graduated hints (levels 1-3).

Escalates support when student is stuck, using course content for contextual hints.
"""

from langfuse.decorators import observe

from src.llm.state.models import GraphState
from src.llm.objects.LLMs import LLM
from src.llm.prompts.prompt_loader import load_prompt

# Load prompt once at module level
SOCRATIC_HINTING_PROMPT = load_prompt("socratic_hinting")


@observe()
def socratic_hinting(state: GraphState) -> GraphState:
    """
    Provides graduated hints when student is stuck.
    
    Purpose:
    - Give progressively more specific hints (3 levels)
    - Use retrieved course content to ground hints in actual material
    - Reduce frustration while maintaining learning-by-discovery
    - Decide when to escalate to full explanation
    
    Hint Levels:
    - Level 1: Gentle nudge (point to relevant concept area)
    - Level 2: More specific (narrow down the solution space)
    - Level 3: Very specific (almost giving answer, last step before explanation)
    
    Strategy:
    - Retrieval already done in core, use existing reranked chunks
    - Increment hint_level with each call
    - Generate hint based on current level
    - Reduce stuckness_score (giving hint reduces frustration)
    
    Flow Transitions:
    - hint_level < 3 → back to "core" (give student chance to try with hint)
    - hint_level == 3 AND contract.allow_explain → "explain" 
    - hint_level == 3 AND NOT allow_explain → back to "core" with final hint
    
    Changes:
    - Increments hint_level (max 3)
    - Sets socratic_mode for next step
    - Reduces stuckness_score slightly
    - Sets answer with graduated hint
    
    Args:
        state: Current graph state with reranked chunks, hint_level, contract
        
    Returns:
        Updated state with hint and routing decision
    """
    hint_level = state.get("hint_level", 0)
    learning_objective = state.get("learning_objective", "")
    contract = state.get("socratic_contract", {})
    reranked_chunks = state.get("reranked", [])
    user_query = state["user_query"]
    chat_history = state.get("chat_history", [])
    model = state.get("model", "gpt-4o-mini")
    
    # Increment hint level (max 3)
    new_hint_level = min(3, hint_level + 1)
    
    # Prepare context for LLM
    course_materials = "\n\n".join([
        f"[Material {i+1}]\n{chunk.page_content}"
        for i, chunk in enumerate(reranked_chunks[:3])
    ]) if reranked_chunks else "No specific course materials retrieved."
    
    query_for_llm = f"""Learning Objective: {learning_objective}

Hint Level: {new_hint_level}

Student's Current Response: {user_query}

Retrieved Course Materials:
{course_materials}"""
    
    # Generate hint using LLM
    _llm = LLM()
    llm_response = _llm.chat(
        query=query_for_llm,
        chat_history=chat_history,
        model=model,
        system_prompt=SOCRATIC_HINTING_PROMPT
    )
    
    if llm_response.content is None:
        # Fallback if LLM fails
        hint_text = f"💡 **Hinweis {new_hint_level}:** Denke nochmal über die Grundkonzepte nach."
    else:
        hint_text = llm_response.content.strip()
    
    # Determine next mode based on hint level
    if new_hint_level < 3:
        next_mode = "core"  # Back to core for another attempt
    else:
        # Level 3: Check if we should escalate to explain
        if contract.get("allow_explain", False):
            next_mode = "explain"
        else:
            next_mode = "core"
    
    # Reduce stuckness after providing hint (hints reduce frustration)
    current_stuckness = state.get("stuckness_score", 0.0)
    new_stuckness = max(0.0, current_stuckness - 0.2)
    
    # Reset attempt counter (fresh start after hint)
    new_attempt_count = 0
    
    return {
        **state,
        "hint_level": new_hint_level,
        "socratic_mode": next_mode,
        "stuckness_score": new_stuckness,
        "attempt_count": new_attempt_count,
        "answer": hint_text,
    }
