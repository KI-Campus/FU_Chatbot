"""
Node for decomposing complex queries into sub-queries (Multi-Hop).

TODO: Implement LLM-based query decomposition logic.
"""

from langfuse.decorators import observe

from src.llm.state.models import GraphState


@observe()
def decompose_query(state: GraphState) -> GraphState:
    """
    Decomposes complex query into multiple sub-queries for multi-hop retrieval.
    
    PLACEHOLDER: Currently returns single query as-is.
    Future implementation should use LLM to break down complex questions.
    
    Changes:
    - Future: Sets state.sub_queries (list of decomposed queries)
    
    Args:
        state: Current graph state with contextualized_query
        
    Returns:
        Updated state (currently unchanged, placeholder)
    """
    # TODO: Implement LLM call to decompose query
    # Example logic:
    # 1. Use LLM to identify if query requires multiple retrieval steps
    # 2. Break down into sub-questions (e.g., "Compare X and Y" -> ["What is X?", "What is Y?"])
    # 3. Store in state.sub_queries
    
    # Placeholder: No decomposition yet
    return state