"""
Socratic Diagnose Node - Assesses student's current understanding and identifies learning objective.

Second step in socratic workflow: Diagnostic assessment to establish baseline.
"""

from langfuse.decorators import observe

from src.llm.objects.LLMs import LLM, Models
from src.llm.prompts.prompt_loader import load_prompt
from src.llm.state.models import GraphState

# Load prompt once at module level
DIAGNOSE_PROMPT = load_prompt("socratic_diagnose_prompt")

# Constants for fallback learning objective generation
MAX_QUERY_LENGTH = 100  # Maximum length of user query in fallback objective
TRUNCATION_SUFFIX_LENGTH = 3  # Length of "..." suffix


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
    
    # Extract model from runtime_config
    model = state["runtime_config"].get("model", Models.GPT4)
    
    # Use LLM to intelligently extract learning objective from query
    _llm = LLM()
    response = _llm.chat(
        query=user_query,
        chat_history=chat_history,
        model=model,
        system_prompt=DIAGNOSE_PROMPT
    )
    
    if response.content is None or response.content.strip() == "":
        # Fallback to simple heuristic if LLM fails
        # Truncate long queries to keep objectives concise
        if len(user_query) <= MAX_QUERY_LENGTH:
            query_truncated = user_query
        else:
            truncate_at = MAX_QUERY_LENGTH - TRUNCATION_SUFFIX_LENGTH
            query_truncated = user_query[:truncate_at] + "..."
        learning_objective = f"Verstehen: {query_truncated}"
    else:
        learning_objective = response.content.strip()
    
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
