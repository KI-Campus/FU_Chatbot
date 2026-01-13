"""
Node wrapper for retrieving relevant chunks from vector database.
"""

from langfuse.decorators import observe, langfuse_context

from src.llm.objects.retriever import KiCampusRetriever
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
def retrieve_chunks(state: GraphState) -> GraphState:
    """
    Retrieves relevant document chunks using hybrid search.
    
    Changes:
    - Sets state.retrieved (list of TextNode)
    
    Args:
        state: Current graph state with contextualized_query and optional course_id/module_id in runtime_config
        
    Returns:
        Updated state with retrieved chunks
    """
    retriever = KiCampusRetriever(use_hybrid=True)
    
    # Extract optional filters from runtime_config (set by frontend)
    course_id = state["runtime_config"].get("course_id")
    module_id = state["runtime_config"].get("module_id")
    
    # Retrieve chunks using hybrid search (returns TextNode directly)
    nodes = retriever.retrieve(
        query=state["contextualized_query"],
        course_id=course_id,
        module_id=module_id
    )
    
    # Add serialized nodes to Langfuse observation for better tracing
    langfuse_context.update_current_observation(
        output={"retrieved_count": len(nodes), "nodes": serialize_nodes_for_langfuse(nodes)}
    )
    
    return {**state, "retrieved": nodes}