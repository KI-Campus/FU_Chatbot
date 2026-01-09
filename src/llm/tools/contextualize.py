"""
Node wrapper for contextualizing user query and routing to appropriate scenario.
"""

from langfuse.decorators import observe

from llm.objects.contextualizer import Contextualizer
from llm.objects.LLMs import Models
from llm.state.models import GraphState
from llm.state.routing import classify_scenario


@observe()
def contextualize_and_route(state: GraphState) -> GraphState:
    """
    Contextualizes user query with chat history and determines routing scenario.
    
    Changes:
    - Sets state.contextualized_query
    - Sets state.mode (routing decision)
    
    Args:
        state: Current graph state with user_query, chat_history, config
        
    Returns:
        Updated state with contextualized_query and mode
    """
    contextualizer = Contextualizer()
    
    # Extract model from runtime_config (fallback to default)
    model = state.runtime_config.get("model", Models.GPT_4O_MINI)
    
    # Contextualize query using existing logic
    contextualized_query = contextualizer.contextualize(
        query=state.user_query,
        chat_history=state.chat_history,
        model=model
    )
    
    # Determine routing scenario
    mode = classify_scenario(
        query=contextualized_query,
        chat_history_length=len(state.chat_history)
    )
    
    # Update state
    state.contextualized_query = contextualized_query
    state.mode = mode
    
    return state