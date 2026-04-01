from langfuse.decorators import observe

@observe(name="socratic_reflection")
def generate_reflection_text(learning_objective: str | None = None) -> str:
    """
    Helper function to generate reflection text after goal achievement.
    
    Args:
        learning_objective: The learning goal that was achieved
        
    Returns:
        str: Generated reflection text
    """
    
    # Positive reinforcement
    encouragement = (
            "🎓 **Ausgezeichnet!** Du hast das Konzept eigenständig erarbeitet. Das ist der beste Weg zum tiefen Verständnis!"
        )
    
    if learning_objective:
        return (
            f"{encouragement}\n\n"
            f"Du hast das Lernziel '{learning_objective}' erreicht.\n"
            "Was war dein wichtigster Erkenntnisschritt auf dem Weg dorthin?"
        )

    return (
        f"{encouragement}\n\n"
        "Was war dein wichtigster Erkenntnisschritt in dieser Lernrunde?"
    )