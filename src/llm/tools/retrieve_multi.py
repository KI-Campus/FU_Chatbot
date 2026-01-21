"""
Node wrapper for parallel retrieval of multiple sub-queries (Multi-Hop).
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from langfuse.decorators import observe

from src.llm.state.models import GraphState

# Module-level singleton
_retriever_instance = None

def get_retriever(use_hybrid: bool = True, n_chunks: int = 10):
    """Get or create singleton retriever instance."""
    global _retriever_instance
    if _retriever_instance is None:
        from src.llm.objects.retriever import KiCampusRetriever
        _retriever_instance = KiCampusRetriever(use_hybrid=use_hybrid, n_chunks=n_chunks)
    return _retriever_instance


@observe()
def retrieve_multi_parallel(state: GraphState) -> dict:
    """
    Retrieves relevant chunks for all sub-queries in parallel.
    
    Uses ThreadPoolExecutor to execute multiple retrieval calls simultaneously,
    significantly reducing total latency compared to sequential processing.
    
    Changes:
    - Sets state["multi_contexts"] (list of lists of TextNode, one per sub-query)
    
    Args:
        state: Current graph state with sub_queries and optional filters in runtime_config
        
    Returns:
        Updated state with multi_contexts
    """
    # Guard: If no sub_queries, skip
    if "sub_queries" not in state or not state["sub_queries"]:
        return {"multi_contexts": []}
    
    # Get necessary variables from state
    course_id = state["runtime_config"]["course_id"]
    module_id = state["runtime_config"]["module_id"]
    retrieve_top_n = state["system_config"]["retrieve_top_n"]
    
    # Get singleton retriever
    retriever = get_retriever(use_hybrid=True, n_chunks=retrieve_top_n)
    
    # Define retrieval function for parallel execution
    def retrieve_for_query(sub_query: str):
        """Retrieve chunks for a single sub-query."""
        return retriever.retrieve(
            query=sub_query,
            course_id=course_id,
            module_id=module_id
        )
    
    # Execute all retrievals in parallel
    multi_contexts = []
    with ThreadPoolExecutor(max_workers=min(len(state["sub_queries"]), 5)) as executor:
        # Submit all tasks
        future_to_query = {
            executor.submit(retrieve_for_query, sq): sq 
            for sq in state["sub_queries"]
        }
        
        # Collect results in order of completion (then sort by original order)
        results = {}
        for future in as_completed(future_to_query):
            query = future_to_query[future]
            try:
                results[query] = future.result()
            except Exception as e:
                # If retrieval fails for a sub-query, use empty list
                print(f"Retrieval failed for sub-query '{query}': {e}")
                results[query] = []
        
        # Restore original order
        for sq in state["sub_queries"]:
            multi_contexts.append(results.get(sq, []))
    
    # Already SerializableTextNode from retriever
    return {"multi_contexts": multi_contexts}