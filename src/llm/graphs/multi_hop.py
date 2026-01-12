"""
Multi-Hop Subgraph - Complex queries requiring multiple retrieval steps.

For questions that need information from multiple diverse documents
(e.g., comparisons, synthesis, multi-step reasoning).

Flow:
1. Decompose complex query into sub-queries
2. Retrieve chunks for ALL sub-queries in parallel (low latency)
3. Synthesize: Combine and deduplicate all retrieved contexts
4. Rerank: Select most relevant chunks for the original query
5. Generate answer with citations
"""

from langgraph.graph import StateGraph, START, END

from src.llm.state.models import GraphState
from src.llm.tools.decompose import decompose_query
from src.llm.tools.retrieve_multi import retrieve_multi_parallel
from src.llm.tools.synthesize import synthesize_answer
from src.llm.tools.rerank import rerank_chunks
from src.llm.tools.language import detect_language
from src.llm.tools.answer import generate_answer
from src.llm.tools.citation import parse_citations


def build_multi_hop_graph() -> StateGraph:
    """
    Builds the multi_hop subgraph for complex queries.
    
    Flow:
    START → decompose → retrieve_multi_parallel → synthesize → rerank 
          → detect_language → answer → citation → END
    
    Key features:
    - decompose_query: Breaks complex query into self-contained sub-queries
    - retrieve_multi_parallel: Retrieves chunks for all sub-queries simultaneously
    - synthesize_answer: Combines and deduplicates all contexts
    - rerank_chunks: Selects top-N most relevant for original query
    """
    graph = StateGraph(GraphState)
    
    # Add nodes
    graph.add_node("decompose_node", decompose_query)
    graph.add_node("retrieve_multi_node", retrieve_multi_parallel)
    graph.add_node("synthesize_node", synthesize_answer)
    graph.add_node("rerank_node", rerank_chunks)
    graph.add_node("detect_language_node", detect_language)
    graph.add_node("answer_node", generate_answer)
    graph.add_node("citation_node", parse_citations)
    
    # Linear flow with parallel retrieval
    graph.add_edge(START, "decompose_node")
    graph.add_edge("decompose_node", "retrieve_multi_node")
    graph.add_edge("retrieve_multi_node", "synthesize_node")
    graph.add_edge("synthesize_node", "rerank_node")
    graph.add_edge("rerank_node", "detect_language_node")
    graph.add_edge("detect_language_node", "answer_node")
    graph.add_edge("answer_node", "citation_node")
    graph.add_edge("citation_node", END)
    
    return graph.compile()