"""
Simple Hop Subgraph - Classic RAG workflow.

For specific factual questions answerable with a single retrieval step.
This is the standard RAG flow equivalent to the current system.
"""

from langgraph.graph import StateGraph, START, END

from llm.state.models import GraphState
from llm.tools.retrieve import retrieve_chunks
from llm.tools.rerank import rerank_chunks
from llm.tools.language import detect_language
from llm.tools.answer import generate_answer
from llm.tools.citation import parse_citations


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
    
    # Add nodes (using imported node functions from tools/)
    graph.add_node("retrieve", retrieve_chunks)
    graph.add_node("rerank", rerank_chunks)
    graph.add_node("detect_language", detect_language)
    graph.add_node("answer", generate_answer)
    graph.add_node("citation", parse_citations)
    
    # Define linear flow
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "rerank")
    graph.add_edge("rerank", "detect_language")
    graph.add_edge("detect_language", "answer")
    graph.add_edge("answer", "citation")
    graph.add_edge("citation", END)
    
    return graph.compile()