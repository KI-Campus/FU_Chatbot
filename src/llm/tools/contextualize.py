"""
Node wrapper for contextualizing user query and routing to appropriate scenario.
"""

from langfuse.decorators import observe

from src.llm.objects.contextualizer import Contextualizer
from src.llm.state.models import GraphState
from src.llm.state.routing import classify_scenario
from src.llm.state.socratic_routing import should_continue_socratic, reset_socratic_state


@observe()
def contextualize_and_route(state: GraphState) -> GraphState:
    """
    Routes user query to appropriate scenario and contextualizes with chat history.
    
    Socratic Mode Handling:
    1. Check if socratic_mode is active
    2. If yes: Use LLM to check if user wants to continue or exit
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
        Updated state with mode and contextualized_query
    """
    contextualizer = Contextualizer()
    
    # Extract config
    model = state["runtime_config"]["model"]
    user_query = state["user_query"]
    chat_history = state["chat_history"]
    
    # Check if socratic_mode is active
    socratic_mode = state.get("socratic_mode", None)
    
    if socratic_mode is not None and socratic_mode != "complete":
        # Socratic mode is active - check if user wants to continue
        continue_socratic = should_continue_socratic(user_query, chat_history, model)
        
        if not continue_socratic:
            # User wants to exit - clear socratic_mode and reroute
            mode = classify_scenario(query=user_query, chat_history=chat_history, model=model)
            
            # Contextualize normally
            if mode == "no_vectordb":
                contextualized_query = user_query
            else:
                contextualized_query = contextualizer.contextualize(
                    query=user_query,
                    chat_history=chat_history,
                    model=model
                )
            
            # Reset all socratic state (user exited)
            socratic_reset = reset_socratic_state()
            
            # Return with socratic state cleared and new mode
            return {
                **state,
                **socratic_reset,  # Reset all socratic fields
                "mode": mode,
                "contextualized_query": contextualized_query,
            }
        else:
            # User wants to continue socratic
            mode = "socratic"
            
            # Contextualize only if in core mode (retrieval needed)
            if socratic_mode == "core" or socratic_mode == "explain":
                # Use socratic-specific contextualization
                learning_objective = state["learning_objective"]
                contextualized_query = contextualizer.contextualize_socratic(
                    query=user_query,
                    chat_history=chat_history,
                    model=model,
                    learning_objective=learning_objective
                )
            else:
                # For contract, diagnose, hinting, reflection, explain: no contextualization needed
                contextualized_query = user_query
            
            # Keep socratic_mode as-is (managed by socratic nodes)
            return {
                **state,
                "mode": mode,
                "contextualized_query": contextualized_query,
            }
    else:
        # Normal mode (no active socratic session)
        mode = classify_scenario(query=user_query, chat_history=chat_history, model=model)
        
        # Contextualize query if needed
        if mode == "no_vectordb":
            contextualized_query = user_query
        else:
            contextualized_query = contextualizer.contextualize(
                query=user_query,
                chat_history=chat_history,
                model=model
            )
        
        # Build updated state
        updated_state = {
            **state,
            "mode": mode,
            "contextualized_query": contextualized_query,
        }
        
        # Initialize socratic_mode if entering socratic workflow
        if mode == "socratic":
            updated_state["socratic_mode"] = "contract"
        
        return updated_state