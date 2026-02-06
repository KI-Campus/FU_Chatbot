"""
Node wrapper for parallel retrieval of multiple sub-queries (Multi-Hop).
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List
from src.api.models.serializable_text_node import SerializableTextNode
from langfuse.decorators import observe

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
def retrieve_multi_parallel_eval(subqueries: List[str], course_id: int, module_id: int, retrieve_top_n: int) -> List[SerializableTextNode]:
    """
    Retrieves relevant chunks for all sub-queries in parallel.
    
    Uses ThreadPoolExecutor to execute multiple retrieval calls simultaneously,
    significantly reducing total latency compared to sequential processing.
    
    Changes:
    - Sets state["multi_contexts"] (list of lists of TextNode, one per sub-query)
    
    Args:
        subqueries: List of sub-queries to retrieve context for
        course_id: ID of the course for retrieval context
        module_id: ID of the module for retrieval context
        retrieve_top_n: Number of top chunks to retrieve per sub-query
        
    Returns:
        Updated state with multi_contexts
    """
    
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
    with ThreadPoolExecutor(max_workers=min(len(subqueries), 5)) as executor:
        # Submit all tasks
        future_to_query = {
            executor.submit(retrieve_for_query, sq): sq 
            for sq in subqueries
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
        for sq in subqueries:
            multi_contexts.append(results.get(sq, []))
    
    # Already SerializableTextNode from retriever
    return multi_contexts