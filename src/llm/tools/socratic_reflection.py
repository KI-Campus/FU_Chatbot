def generate_reflection_text() -> str:
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
    
    # Reflection prompts to consolidate learning
    #Kept empty for now, can be expanded later
    reflection_prompts = "" 
    
    # Closing and next steps
    closing = "\nFalls du weiterhin im Lernmodus bleiben möchtest, lasse mich wissen, bei welchem Thema ich dir weiterhin helfen kann! Andernfalls verlasse den Lernmodus mit 'quit'."
    
    full_response = encouragement + reflection_prompts + closing
    
    return full_response