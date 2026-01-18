"""
Simple Hop Subgraph - Classic RAG workflow.

For specific factual questions answerable with a single retrieval step.
This is the standard RAG flow equivalent to the current system.
"""

from langgraph.graph import StateGraph, START, END

from src.llm.state.models import GraphState
from src.llm.tools.retrieve import retrieve_chunks
from src.llm.tools.rerank import rerank_chunks
from src.llm.tools.language import detect_language
from src.llm.tools.answer import generate_answer
from src.llm.tools.citation import parse_citations


def build_simple_hop_graph() -> StateGraph:
    """
    Builds the simple_hop subgraph for standard RAG queries.
    
    Flow:
    START → retrieve → rerank → detect_language → answer → citation → END
    
    This is the classic RAG pipeline:
    1. Retrieve relevant chunks using hybrid search
    2. Rerank for precision
    3. Detect user's language
    4. Generate answer with sources
    5. Parse citations into clickable links
    """
    graph = StateGraph(GraphState)
    
    # Add nodes
    graph.add_node("retrieve_node", retrieve_chunks)
    graph.add_node("rerank_node", rerank_chunks)
    graph.add_node("detect_language_node", detect_language)
    graph.add_node("answer_node", generate_answer)
    graph.add_node("citation_node", parse_citations)
    
    # Define linear flow
    graph.add_edge(START, "retrieve_node")
    graph.add_edge("retrieve_node", "rerank_node")
    graph.add_edge("rerank_node", "detect_language_node")
    graph.add_edge("detect_language_node", "answer_node")
    graph.add_edge("answer_node", "citation_node")
    graph.add_edge("citation_node", END)
    
    return graph.compile()