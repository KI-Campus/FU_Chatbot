"""
Node wrapper for reranking retrieved chunks.
"""

from langfuse.decorators import observe

from src.llm.objects.reranker import Reranker
from src.llm.state.models import GraphState


@observe()
def rerank_chunks(state: GraphState) -> GraphState:
    """
    Reranks retrieved chunks using LLM for improved precision.
    
    Changes:
    - Sets state.reranked (list of top-N reranked TextNodes)
    
    Args:
        state: Current graph state with contextualized_query, retrieved, and configs
        
    Returns:
        Updated state with reranked chunks
    """
    # Extract config
    model = state["runtime_config"].get("model")
    rerank_top_n = state["system_config"].get("rerank_top_n", 5)
    
    # Guard: If no documents retrieved or too few for reranking, skip reranking
    if not state["retrieved"] or len(state["retrieved"]) == 0:
        return {**state, "reranked": []}
    
    # If only 1 node, no need to rerank
    if len(state["retrieved"]) == 1:
        return {**state, "reranked": state["retrieved"]}
    
    # Initialize reranker
    reranker = Reranker(top_n=rerank_top_n)
    
    # Rerank (works directly with TextNode)
    reranked_nodes = reranker.rerank(
        query=state["contextualized_query"],
        nodes=state["retrieved"],
        model=model
    )
    
    return {**state, "reranked": reranked_nodes}