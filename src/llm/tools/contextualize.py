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
    Routes user query to appropriate scenario and contextualizes with chat history.
    
    Order: Route first (on original query), then contextualize.
    Routing should be based on the original user query, not the contextualized one.
    
    Changes:
    - Sets state["mode"] (routing decision based on original query)
    - Sets state["contextualized_query"] (contextualized with chat history)
    
    Args:
        state: Current graph state with user_query, chat_history, config
        
    Returns:
        Updated state with mode and contextualized_query
    """
    contextualizer = Contextualizer()
    
    # Extract model from runtime_config
    model = state["runtime_config"].get("model")
    
    # 1. Determine routing scenario
    mode = classify_scenario(
        query=state["user_query"],
        model=model
    )
    
    # 2. Contextualize query if needed
    if mode == "no_vectordb":
        # No need to contextualize for no_vectordb
        contextualized_query = state["user_query"]
    else:
        contextualized_query = contextualizer.contextualize(
            query=state["user_query"],
            chat_history=state["chat_history"],
            model=model
        )
    
    # Update state and return
    return {
        **state,
        "mode": mode,
        "contextualized_query": contextualized_query,
    }