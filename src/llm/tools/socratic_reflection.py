"""
Socratic Reflection Node - Consolidates learning after goal achievement.

Final step in socratic workflow: Helps student internalize and generalize what they learned.
"""

from langfuse.decorators import observe

from src.llm.state.models import GraphState


@observe()
def socratic_reflection(state: GraphState) -> GraphState:
    """
    Guides student through reflection after achieving learning objective.
    
    Purpose:
    - Help student articulate what they learned in their own words
    - Connect learning to broader concepts and principles
    - Encourage metacognition (thinking about thinking)
    - Facilitate transfer to new contexts
    - Provide closure to the learning session
    
    Reflection Components:
    - Journey summary (how student got to understanding)
    - Key insights (what was the breakthrough moment)
    - Self-explanation (articulate learning in own words)
    - Transfer (where else could this apply)
    
    Strategy:
    - Summarize the learning path
    - Ask reflective questions
    - Encourage generalization
    - Provide positive reinforcement
    
    Flow:
    - Terminal state: No further transitions (END)
    - Session complete, student can start new query if desired
    
    Changes:
    - Sets answer with reflection guidance
    - Marks socratic_mode as "complete" (for analytics)
    - Updates student_model with final assessment
    
    Args:
        state: Current graph state with learning_objective, student_model, chat_history
        
    Returns:
        Updated state with reflection guidance (terminal state)
    """
    learning_objective = state.get("learning_objective", "")
    student_model = state.get("student_model", {})
    chat_history = state.get("chat_history", [])
    hint_level = state.get("hint_level", 0)
    attempt_count = state.get("attempt_count", 0)
    
    # Determine learning path (self-discovered vs explained)
    mastery_level = student_model.get("mastery", "unknown")
    learning_path = student_model.get("learning_path", "socratic_discovery")
    
    # Positive reinforcement based on how they got here
    if mastery_level == "explained":
        encouragement = (
            "🎓 **Sehr gut!** Du hast durchgehalten, auch als es schwierig wurde. "
            "Das zeigt echte Lernbereitschaft!"
        )
    else:
        encouragement = (
            "🎓 **Ausgezeichnet!** Du hast das Konzept eigenständig erarbeitet. "
            "Das ist der beste Weg zum tiefen Verständnis!"
        )
    
    # Reflection prompts to consolidate learning
    reflection_prompts = (
        f"\n\n**Lass uns kurz reflektieren, um das Gelernte zu festigen:**\n\n"
        f"1️⃣ **Dein Aha-Moment:**\n"
        f"   Was war der entscheidende Durchbruch für dich? Was hat \"Klick\" gemacht?\n\n"
        f"2️⃣ **In eigenen Worten:**\n"
        f"   Wie würdest du das Gelernte jemandem erklären, der noch gar nichts davon weiß?\n\n"
        f"3️⃣ **Breitere Anwendung:**\n"
        f"   Wo könnte dieses Prinzip noch nützlich sein? "
        f"In welchen anderen Situationen könntest du es anwenden?\n\n"
        f"4️⃣ **Was noch offen ist:**\n"
        f"   Gibt es noch Aspekte, die du vertiefen möchtest? "
        f"Welche Fragen sind noch offen?\n\n"
    )
    
    # Closing and next steps
    closing = (
        "\n📚 **Zusammenfassung:**\n"
        f"Wir haben gemeinsam an deinem Ziel gearbeitet: *{learning_objective}*\n\n"
        "Nimm dir einen Moment, über diese Fragen nachzudenken. "
        "Das hilft dir, das Wissen wirklich zu verinnerlichen und auf neue Situationen anzuwenden.\n\n"
        "Wenn du bereit bist, können wir gerne ein anderes Thema angehen oder "
        "tiefer in verwandte Konzepte eintauchen. Du entscheidest! 💪"
    )
    
    full_response = encouragement + reflection_prompts + closing
    
    # Update student model with final state
    updated_student_model = {
        **student_model,
        "session_completed": True,
        "reflection_provided": True,
        "final_assessment": "goal_achieved",
    }
    
    # Mark as complete (terminal state for analytics)
    # This signals end of socratic workflow
    final_mode = "complete"
    
    return {
        **state,
        "student_model": updated_student_model,
        "socratic_mode": final_mode,
        "answer": full_response,
    }
