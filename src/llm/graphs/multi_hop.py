"""
Multi-Hop Subgraph - Complex queries requiring multiple retrieval steps.

For questions that need information from multiple diverse documents
(e.g., comparisons, synthesis, multi-step reasoning).

NOTE: Currently uses simple_hop flow as placeholder.
Future implementation will decompose queries and perform multiple retrieval rounds.
"""

from langgraph.graph import StateGraph, START, END

from llm.state.models import GraphState
from llm.tools.decompose import decompose_query
from llm.tools.retrieve import retrieve_chunks
from llm.tools.rerank import rerank_chunks
from llm.tools.synthesize import synthesize_answer
from llm.tools.language import detect_language
from llm.tools.answer import generate_answer
from llm.tools.citation import parse_citations


def build_multi_hop_graph() -> StateGraph:
    """
    Builds the multi_hop subgraph for complex queries.
    
    PLACEHOLDER Flow (currently same as simple_hop):
    START → retrieve → rerank → detect_language → answer → citation → END
    
    FUTURE Flow (to be implemented):
    START → decompose → [retrieve → rerank] (loop) → synthesize → detect_language → answer → citation → END
    
    Future enhancements:
    - decompose_query: Break complex query into sub-queries
    - Conditional loop: Retrieve for each sub-query
    - synthesize_answer: Combine contexts from multiple retrievals
    """
    graph = StateGraph(GraphState)
    
    # TODO: Add decompose and synthesize nodes once implemented
    # For now, use standard RAG flow
    
    graph.add_node("retrieve", retrieve_chunks)
    graph.add_node("rerank", rerank_chunks)
    graph.add_node("detect_language", detect_language)
    graph.add_node("answer", generate_answer)
    graph.add_node("citation", parse_citations)
    
    # Linear flow (placeholder - will become branched with loops later)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "rerank")
    graph.add_edge("rerank", "detect_language")
    graph.add_edge("detect_language", "answer")
    graph.add_edge("answer", "citation")
    graph.add_edge("citation", END)
    
    return graph.compile()