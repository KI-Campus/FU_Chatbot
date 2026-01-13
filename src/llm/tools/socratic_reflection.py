"""
Socratic Reflection Node - Consolidates learning after goal achievement.

Final step in socratic workflow: Helps student internalize and generalize what they learned.
"""

from langfuse.decorators import observe

from src.llm.state.models import GraphState

@observe()
def generate_reflection_text(
    learning_objective: str,
    student_model: dict
) -> tuple[str, dict]:
    """
    Helper function to generate reflection text after goal achievement.
    
    Args:
        learning_objective: The learning goal that was achieved
        student_model: Current student model state
        
    Returns:
        Tuple of (reflection_text, updated_student_model)
    """
    mastery_level = student_model.get("mastery", "unknown")
    
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
    #Kept empty for now, can be expanded later
    reflection_prompts = "" 
    
    # Closing and next steps
    closing = (
        "Wenn du bereit bist, können wir gerne ein anderes Thema angehen oder "
        "tiefer in verwandte Konzepte eintauchen. Du entscheidest!"
    )
    
    full_response = encouragement + reflection_prompts + closing
    
    # Update student model with final state
    updated_student_model = {
        **student_model,
        "session_completed": True,
        "reflection_provided": True,
        "final_assessment": "goal_achieved",
    }
    
    return full_response, updated_student_model