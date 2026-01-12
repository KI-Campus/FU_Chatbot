"""
Node wrapper for parallel retrieval of multiple sub-queries (Multi-Hop).
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from langfuse.decorators import observe

from src.llm.objects.retriever import KiCampusRetriever
from src.llm.state.models import GraphState


@observe()
def retrieve_multi_parallel(state: GraphState) -> GraphState:
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
        return {**state, "multi_contexts": []}
    
    # Initialize retriever
    retriever = KiCampusRetriever(use_hybrid=True)
    
    # Extract optional filters from runtime_config
    course_id = state["runtime_config"].get("course_id")
    module_id = state["runtime_config"].get("module_id")
    
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
    
    return {**state, "multi_contexts": multi_contexts}
