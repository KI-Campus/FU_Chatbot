"""
Socratic Hinting Node - Provides graduated hints (levels 1-3).

Escalates support when student is stuck, using course content for contextual hints.
"""

from langfuse.decorators import observe

from src.llm.state.models import GraphState


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
    
    # Increment hint level (max 3)
    new_hint_level = min(3, hint_level + 1)
    
    # Generate hint based on level
    # TODO Phase 11: Use LLM + reranked chunks to generate contextual hints
    # For now, use template-based hints with different specificity levels
    
    if new_hint_level == 1:
        # Level 1: General direction, point to concept area
        hint_text = (
            "💡 **Hinweis 1:**\n\n"
            "Denke an die grundlegenden Konzepte, die wir besprochen haben. "
            "Welches dieser Konzepte könnte hier besonders relevant sein?\n\n"
            "Nimm dir einen Moment und versuche es nochmal mit diesem Gedanken im Hinterkopf."
        )
        next_mode = "core"  # Back to core for another attempt
        
    elif new_hint_level == 2:
        # Level 2: More specific, narrow down solution space
        hint_text = (
            "💡 **Hinweis 2:**\n\n"
            "Gut, du bist auf dem richtigen Weg! Lass uns konkreter werden:\n\n"
            "Betrachte den Zusammenhang zwischen den verschiedenen Komponenten. "
            "Wie beeinflussen sie sich gegenseitig? Was passiert Schritt für Schritt?\n\n"
            "Versuche, den Prozess in kleinere Teile zu zerlegen."
        )
        next_mode = "core"  # Back to core for another attempt
        
    else:  # Level 3
        # Level 3: Very specific, almost giving the answer
        hint_text = (
            "💡 **Hinweis 3:**\n\n"
            "Okay, lass mich sehr konkret werden:\n\n"
            "Der Schlüssel liegt in [spezifischer Aspekt des Konzepts]. "
            "Versuche, dieses Prinzip direkt auf deine Ausgangsfrage anzuwenden.\n\n"
            "Wenn du jetzt immernoch unsicher bist, kann ich dir auch eine "
            "vollständige Erklärung geben – sag einfach Bescheid!"
        )
        
        # Check if we should escalate to explain
        # Only if contract explicitly allows it
        if contract.get("allow_explain", False):
            next_mode = "explain"
        else:
            # Give student one more chance with the strong hint
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
