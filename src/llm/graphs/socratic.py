"""
Socratic Subgraph - Guided learning assistant.

For queries where the user signals desire for step-by-step guidance,
hints, or self-discovery rather than direct answers.

NOTE: Very generic placeholder implementation.
Future versions will include sophisticated pedagogical logic.
"""

from langgraph.graph import StateGraph, START, END

from llm.state.models import GraphState
from llm.tools.retrieve import retrieve_chunks
from llm.tools.rerank import rerank_chunks
from llm.tools.language import detect_language
from llm.tools.socratic import socratic_guide


def build_socratic_graph() -> StateGraph:
    """
    Builds the socratic subgraph for guided learning.
    
    PLACEHOLDER Flow:
    START → detect_language → socratic_guide → END
    
    FUTURE Flow (optional retrieval for grounding):
    START → detect_language → retrieve (conditional) → rerank → socratic_guide → END
    
    Future enhancements:
    - Conditional retrieval: Only retrieve if question needs course content grounding
    - Student modeling: Track understanding across conversation
    - Adaptive scaffolding: Ask/Hint/Explain based on student state
    - Practice generation: Create quiz questions aligned with learning goals
    """
    graph = StateGraph(GraphState)
    
    # Simple flow for now (no retrieval)
    # TODO: Add conditional retrieval when socratic logic is more sophisticated
    
    graph.add_node("detect_language", detect_language)
    graph.add_node("socratic_guide", socratic_guide)
    
    # Linear flow (placeholder)
    graph.add_edge(START, "detect_language")
    graph.add_edge("detect_language", "socratic_guide")
    graph.add_edge("socratic_guide", END)
    
    return graph.compile()