"""
Node wrapper for reranking retrieved chunks.
"""

from langfuse.decorators import observe

from llm.objects.reranker import Reranker
from llm.objects.LLMs import Models
from llm.state.models import GraphState


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
    model = state.runtime_config.get("model", Models.GPT_4O_MINI)
    rerank_top_n = state.system_config.get("rerank_top_n", 5)
    
    # Initialize reranker
    reranker = Reranker(top_n=rerank_top_n)
    
    # Rerank (works directly with TextNode)
    reranked_nodes = reranker.rerank(
        query=state.contextualized_query,
        nodes=state.retrieved,
        model=model
    )
    
    state.reranked = reranked_nodes
    
    return state