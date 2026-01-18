"""
Node for synthesizing contexts from multiple retrieval rounds (Multi-Hop).
"""

from langfuse.decorators import observe

from src.llm.state.models import GraphState


@observe()
def synthesize_answer(state: GraphState) -> dict:
    """
    Synthesizes contexts from multiple sub-query retrievals into unified context.
    
    Combines all retrieved chunks from multiple retrieval rounds,
    deduplicates by node ID, and prepares for reranking.
    
    The reranker will then select the most relevant nodes for the original query.
    
    Changes:
    - Sets state["retrieved"] with combined, deduplicated nodes (for reranking)
    
    Args:
        state: Current graph state with multi_contexts (list of lists of TextNode)
        
    Returns:
        Updated state with combined retrieved nodes for reranking
    """
    # Guard: If no multi_contexts, skip synthesis
    if "multi_contexts" not in state or not state["multi_contexts"]:
        return {"retrieved": []}
    
    # Flatten all contexts (already SerializableTextNode) and deduplicate by id_
    seen_ids = set()
    combined_nodes = []
    
    for context_list in state["multi_contexts"]:
        for node in context_list:
            node_id = node.id_ if node.id_ else id(node)
            if node_id not in seen_ids:
                seen_ids.add(node_id)
                combined_nodes.append(node)
    
    # Pass ALL deduplicated nodes to reranker (it will select top_n)
    # SINNVOLL ODER SOLLTE DER RERANKER GEZWUNGEN WERDEN DOKUMENTE DIE FÜR JEDE SUBQUERY RETRIEVED WURDEN ZU NUTZEN?
    return {"retrieved": combined_nodes}