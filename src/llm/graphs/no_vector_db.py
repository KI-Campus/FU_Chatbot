"""
No Vector DB Subgraph - Conversational queries without retrieval.

For simple conversational messages that don't require knowledge retrieval
(e.g., greetings, acknowledgments, small talk).
"""

from langgraph.graph import StateGraph, START, END

from src.llm.state.models import GraphState
from src.llm.tools.language import detect_language

# Module-level singleton
_question_answerer_instance = None

def get_question_answerer():
    """Get or create singleton question answerer instance."""
    global _question_answerer_instance
    if _question_answerer_instance is None:
        from src.llm.objects.question_answerer import QuestionAnswerer
        _question_answerer_instance = QuestionAnswerer()
    return _question_answerer_instance


def direct_answer_node(state: GraphState) -> dict:
    """
    Generate direct conversational response without retrieval.
    
    For no_vectordb scenario: Simple, friendly responses to conversational queries.
    """
    # Get singleton question answerer
    answerer = get_question_answerer()
    model = state["runtime_config"]["model"]
    query = state["user_query"]
    chat_history = state["chat_history"]
    language = state["detected_language"]
    
    # Simple conversational response (no sources)
    response = answerer.answer_question(
        query=query,
        chat_history=chat_history,
        language=language,
        sources=[],  # No retrieval
        model=model,
        is_moodle=False,
        course_id=None
    )
    
    return {
        "answer": response.content,
    }


def build_no_vectordb_graph() -> StateGraph:
    """
    Builds the no_vectordb subgraph for conversational queries.
    
    Flow:
    START → detect_language → direct_answer → END
    """
    graph = StateGraph(GraphState)
    
    # Add nodes
    graph.add_node("detect_language_node", detect_language)
    graph.add_node("direct_answer_node", direct_answer_node)
    
    # Define linear flow
    graph.add_edge(START, "detect_language_node")
    graph.add_edge("detect_language_node", "direct_answer_node")
    graph.add_edge("direct_answer_node", END)
    
    return graph.compile()