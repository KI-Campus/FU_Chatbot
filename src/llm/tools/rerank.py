"""
Node wrapper for reranking retrieved chunks.
"""

from langfuse.decorators import observe, langfuse_context

from src.llm.objects.reranker import Reranker
from src.llm.state.models import GraphState


def serialize_nodes_for_langfuse(nodes):
    """Extract text and metadata from TextNodes for Langfuse tracing."""
    return [
        {
            "text": node.text[:500] + "..." if len(node.text) > 500 else node.text,  # Limit length
            "score": node.score if hasattr(node, "score") else None,
            "metadata": {
                "source": node.metadata.get("url", "unknown"),
                "course_id": node.metadata.get("course_id"),
                "module_id": node.metadata.get("module_id"),
            }
        }
        for node in (nodes or [])
    ]


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
        langfuse_context.update_current_observation(output={"reranked_count": 0, "nodes": []})
        return {**state, "reranked": []}
    
    # If only 1 node, no need to rerank
    if len(state["retrieved"]) == 1:
        langfuse_context.update_current_observation(
            output={"reranked_count": 1, "nodes": serialize_nodes_for_langfuse(state["retrieved"])}
        )
        return {**state, "reranked": state["retrieved"]}
    
    # Initialize reranker
    reranker = Reranker(top_n=rerank_top_n)
    
    # Rerank (works directly with TextNode)
    reranked_nodes = reranker.rerank(
        query=state["contextualized_query"],
        nodes=state["retrieved"],
        model=model
    )
    
    # Add serialized nodes to Langfuse observation for better tracing
    langfuse_context.update_current_observation(
        output={"reranked_count": len(reranked_nodes), "nodes": serialize_nodes_for_langfuse(reranked_nodes)}
    )
    
    return {**state, "reranked": reranked_nodes}