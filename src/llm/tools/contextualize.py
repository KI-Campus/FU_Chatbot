"""
Node wrapper for contextualizing user query and routing to appropriate scenario.
"""

from langfuse.decorators import observe

from src.llm.objects.contextualizer import Contextualizer
from src.llm.state.models import GraphState
from src.llm.state.routing import classify_scenario


@observe()
def contextualize_and_route(state: GraphState) -> GraphState:
    """
    Contextualizes user query with chat history and determines routing scenario.
    
    Changes:
    - Sets state["contextualized_query"]
    - Sets state["mode"] (routing decision)
    
    Args:
        state: Current graph state with user_query, chat_history, config
        
    Returns:
        Updated state with contextualized_query and mode
    """
    contextualizer = Contextualizer()
    
    # Extract model from runtime_config
    model = state["runtime_config"].get("model")
    
    # Contextualize query using existing logic
    contextualized_query = contextualizer.contextualize(
        query=state["user_query"],
        chat_history=state["chat_history"],
        model=model
    )
    
    # Determine routing scenario
    mode = classify_scenario(
        query=contextualized_query,
        chat_history_length=len(state["chat_history"])
    )
    
    # Update state and return
    return {
        **state,
        "contextualized_query": contextualized_query,
        "mode": mode
    }