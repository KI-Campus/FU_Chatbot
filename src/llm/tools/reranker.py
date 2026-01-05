"""
Reranker for improving retrieval quality using LLM-based reranking.

This reranker takes retrieved nodes and reranks them based on relevance
to the query using an LLM, improving precision over pure vector similarity.
"""

from langfuse.decorators import observe
from llama_index.core.postprocessor import LLMRerank
from llama_index.core.schema import NodeWithScore, TextNode

from src.llm.LLMs import LLM, Models


class Reranker:
    """LLM-based reranker for improving retrieval precision.
    
    Uses LlamaIndex's LLMRerank internally to score and reorder nodes
    based on their relevance to the query.
    """
    
    def __init__(self, top_n: int = 5):
        """Initialize the reranker.
        
        Args:
            top_n: Number of top results to return after reranking
        """
        self.llm = LLM()
        self.top_n = top_n
    
    @observe(name="rerank")
    def rerank(self, query: str, nodes: list[TextNode], model: Models) -> list[TextNode]:
        """Rerank nodes based on query relevance using LLM.
        
        Args:
            query: The user's query
            nodes: List of retrieved nodes to rerank
            model: Which LLM model to use for reranking (from LLM selection logic)
            
        Returns:
            Reranked list of nodes (top_n best matches)
        """
        if not nodes:
            return []
        
        # Get LLM instance for reranking
        llm = self.llm.get_model(model)
        
        # Initialize LLMRerank with chosen model
        llm_rerank = LLMRerank(
            llm=llm,
            top_n=self.top_n,
            choice_batch_size=5,  # Process 5 nodes at a time to avoid token limits
        )
        
        # LLMRerank expects NodeWithScore, convert if needed
        nodes_with_score = []
        for node in nodes:
            if isinstance(node, NodeWithScore):
                nodes_with_score.append(node)
            else:
                # Wrap TextNode in NodeWithScore
                nodes_with_score.append(NodeWithScore(node=node, score=node.score if hasattr(node, 'score') else None))
        
        # Perform reranking
        reranked_nodes = llm_rerank.postprocess_nodes(
            nodes=nodes_with_score,
            query_str=query
        )
        
        # Extract nodes from NodeWithScore
        result_nodes = []
        for node_with_score in reranked_nodes:
            if isinstance(node_with_score, NodeWithScore):
                result_nodes.append(node_with_score.node)
            else:
                result_nodes.append(node_with_score)
        
        return result_nodes
