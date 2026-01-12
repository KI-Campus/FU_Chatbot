"""
Node wrapper for retrieving relevant chunks from vector database.
"""

from langfuse.decorators import observe

from src.llm.objects.retriever import KiCampusRetriever
from src.llm.state.models import GraphState


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
    
    return {**state, "retrieved": nodes}