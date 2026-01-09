"""
No Vector DB Subgraph - Conversational queries without retrieval.

For simple conversational messages that don't require knowledge retrieval
(e.g., greetings, acknowledgments, small talk).
"""

from langgraph.graph import StateGraph, START, END

from llm.state.models import GraphState
from llm.tools.language import detect_language
from llm.objects.question_answerer import QuestionAnswerer
from llm.objects.LLMs import Models


def direct_answer_node(state: GraphState) -> GraphState:
    """
    Generate direct conversational response without retrieval.
    
    For no_vectordb scenario: Simple, friendly responses to conversational queries.
    """
    answerer = QuestionAnswerer()
    model = state.runtime_config.get("model", Models.GPT_4O_MINI)
    
    # Simple conversational response (no sources)
    response = answerer.answer_question(
        query=state.user_query,
        chat_history=state.chat_history,
        language=state.detected_language or "German",
        sources=[],  # No retrieval
        model=model,
        is_moodle=False,
        course_id=None
    )
    
    state.answer = response.content
    state.citations_markdown = response.content  # No citations needed
    
    return state


def build_no_vectordb_graph() -> StateGraph:
    """
    Builds the no_vectordb subgraph for conversational queries.
    
    Flow:
    START → detect_language → direct_answer → END
    """
    graph = StateGraph(GraphState)
    
    # Add nodes
    graph.add_node("detect_language", detect_language)
    graph.add_node("direct_answer", direct_answer_node)
    
    # Define edges
    graph.add_edge(START, "detect_language")
    graph.add_edge("detect_language", "direct_answer")
    graph.add_edge("direct_answer", END)
    
    return graph.compile()