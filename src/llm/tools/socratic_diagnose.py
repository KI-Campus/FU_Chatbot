"""
Socratic Diagnose Node - Assesses student's current understanding and identifies learning objective.

Second step in socratic workflow: Diagnostic assessment to establish baseline.
"""

from langfuse.decorators import observe

from src.llm.state.models import GraphState


@observe()
def socratic_diagnose(state: GraphState) -> GraphState:
    """
    Diagnoses student's current understanding and identifies learning objective.
    
    Purpose:
    - Extract learning objective from user query
    - Assess student's baseline knowledge
    - Initialize student model for tracking progress
    - Ask diagnostic question to gather more context
    
    Flow:
    - Always transitions to "core" next
    
    Changes:
    - Sets learning_objective (extracted from query)
    - Initializes student_model with baseline assessment
    - Sets socratic_mode = "core" for next step
    - Sets answer with diagnostic question
    
    Args:
        state: Current graph state with user_query and chat_history
        
    Returns:
        Updated state with learning objective and student model
    """
    user_query = state["user_query"]
    chat_history = state.get("chat_history", [])
    
    # Extract learning objective from query (simple heuristic for now)
    # TODO Phase 11: Use LLM to intelligently extract learning goal
    learning_objective = f"Verstehen: {user_query}"
    
    # Initialize student model with unknown baseline
    # Will be updated based on student's responses in core loop
    student_model = {
        "mastery": "unknown",  # Will become "low", "medium", or "high" based on responses
        "misconceptions": [],  # Detected misconceptions will be added during core loop
        "affect": "neutral",  # Emotional state: "engaged", "frustrated", "confused", etc.
        "prior_knowledge": None,  # Will be filled from diagnostic response
    }
    
    # Ask diagnostic question to assess baseline knowledge
    # This helps us understand where to start the Socratic dialogue
    diagnostic_question = (
        f"Um dir bestmöglich helfen zu können, möchte ich zuerst verstehen, "
        f"wo du gerade stehst:\n"
        f"**Was weißt du bereits über dieses Thema?**\n"
        f"Beschreibe mir gerne deine bisherigen Gedanken, Überlegungen oder "
        f"was du schon darüber gelernt hast – egal wie viel oder wenig das ist!"
    )
    
    return {
        **state,
        "learning_objective": learning_objective,
        "student_model": student_model,
        "socratic_mode": "core",
        "answer": diagnostic_question,
    }
