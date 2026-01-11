"""
Socratic Explain Node - Provides controlled explanation when Socratic method reaches its limit.

Fallback mechanism when hints don't suffice or student explicitly requests explanation.
"""

from langfuse.decorators import observe

from src.llm.state.models import GraphState


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
    
    # Acknowledge student's effort
    # TODO Phase 11: Analyze chat_history to reference specific student attempts
    acknowledgment = (
        "Ich sehe, du hast dich wirklich bemüht! "
        "Deine bisherigen Überlegungen zeigen, dass du schon einige Aspekte verstanden hast."
    )
    
    # Provide structured explanation
    # TODO Phase 11: Use LLM + reranked chunks to generate grounded explanation
    # Should reference actual course content and student's misconceptions
    explanation = (
        f"\n\n📖 **Erklärung zu: {learning_objective}**\n\n"
        "Lass mich das Konzept nun strukturiert erklären:\n\n"
        "**1. Grundidee:**\n"
        "[Kernkonzept in einfachen Worten]\n\n"
        "**2. Wie es funktioniert:**\n"
        "[Schritt-für-Schritt Ablauf]\n\n"
        "**3. Warum es wichtig ist:**\n"
        "[Praktische Bedeutung und Anwendung]\n\n"
        "**4. Häufige Missverständnisse:**\n"
        "[Was oft verwechselt wird und warum]\n\n"
    )
    
    # Transition to reflection
    reflection_transition = (
        "\n**Lass uns das Gelernte festigen:**\n"
        "Jetzt, wo du die Erklärung gehört hast, lass uns kurz reflektieren, "
        "damit das Wissen wirklich bei dir ankommt."
    )
    
    full_response = acknowledgment + explanation + reflection_transition
    
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
