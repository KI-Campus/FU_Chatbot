"""
Node wrapper for contextualizing user query and routing to appropriate scenario.
"""

from langfuse.decorators import observe

from src.llm.state.models import GraphState, get_chat_history_as_messages
from src.llm.state.socratic_routing import reset_socratic_state
from src.api.models.serializable_chat_message import SerializableChatMessage

# Module-level singleton
_contextualizer_instance = None

def get_contextualizer():
    """Get or create singleton contextualizer instance."""
    global _contextualizer_instance
    if _contextualizer_instance is None:
        from src.llm.objects.contextualizer import Contextualizer
        _contextualizer_instance = Contextualizer()
    return _contextualizer_instance


@observe()
def contextualize_and_route(state: GraphState) -> dict:
    """
    Routes user query to appropriate scenario and contextualizes with chat history.
    
    Socratic Mode Handling:
    1. Check if socratic_mode is active
    2. If yes: Check if user wants to continue or exit
    3. If exit: Set socratic_mode=None and reroute
    4. If continue: Keep socratic, use socratic-specific contextualization (only for core mode)
    
    Order: Route first (on original query), then contextualize.
    
    Changes:
    - Sets state["mode"] (routing decision based on original query)
    - Sets state["contextualized_query"] (contextualized with chat history)
    - Manages state["socratic_mode"] (checks for exit intent)
    
    Args:
        state: Current graph state with user_query, chat_history, config
        
    Returns:
        Updated state with mode and contextualized_query (see Changes)
    """

    # Get singleton contextualizer
    contextualizer = get_contextualizer()
    # Get necessary fields from state
    model = state["runtime_config"]["model"]
    user_query = state["user_query"]
    chat_history_serializable = state.get("chat_history", [])
    chat_history_messages = get_chat_history_as_messages(state)
    socratic_mode = state.get("socratic_mode", None)
    # Cleaned user response for entry/exit intent (socratic mode)
    response_clean = user_query.lower().strip()
    
    # Handle socratic mode if active
    if socratic_mode is not None and socratic_mode != "complete":
        # Socratic mode is active - check if user wants to continue
        continue_socratic = response_clean not in ["exit", "quit", "stop", "stopp"]
        
        if not continue_socratic:
            # User wants to exit - provide prefabricated message and skip LLM call
            
            exit_message = SerializableChatMessage(
                role="assistant",
                content="Du hast den Lernmodus verlassen. Wenn du weitere Fragen hast, stehe ich dir gerne zur Verfügung!"
            )
            
            # Reset all socratic state (user exited)
            socratic_reset = reset_socratic_state()
            
            # Return with prefabricated answer and special mode to skip to END
            return {
                **socratic_reset,  # Reset all socratic fields
                "mode": "exit_complete",
                "final_answer": exit_message,
            }
        else:
            # User wants to continue socratic
            mode = "socratic"
            
            # Contextualize only if in core or explain mode (retrieval needed)
            if socratic_mode == "core" or socratic_mode == "explain":
                # Use socratic-specific contextualization
                learning_objective = state["learning_objective"]
                contextualized_query = contextualizer.contextualize_socratic(
                    query=user_query,
                    chat_history=chat_history_serializable,
                    model=model,
                    learning_objective=learning_objective
                )
            else:
                # For contract, diagnose, hinting, reflection: no contextualization needed
                contextualized_query = None
            
            # Keep socratic_mode as-is (managed by socratic nodes)
            return {
                "mode": mode,
                "contextualized_query": contextualized_query,
            }
    else:
        # Normal mode handling (no active socratic session)
        # Check if user wants to start socratic mode
        if response_clean in ["start socratic", "begin socratic", "enter socratic"]:
            return {
                "mode": "socratic",
                "socratic_mode": "contract"
            }
        
        # Classify scenario based on original query
        mode = contextualizer.classify_scenario(query=user_query, model=model)
        
        # Contextualize query if needed
        if mode == "no_vectordb" or mode == "multi_hop":
            contextualized_query = None
        else:
            contextualized_query = contextualizer.contextualize(
                query=user_query,
                chat_history=chat_history_messages,
                model=model
            )
        
        return {
            "mode": mode,
            "contextualized_query": contextualized_query,
        }