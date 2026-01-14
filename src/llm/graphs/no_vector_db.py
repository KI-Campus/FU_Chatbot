from langgraph.graph import StateGraph, START, END

from src.llm.state.models import GraphState
from src.llm.tools.language import detect_language
from src.llm.objects.question_answerer import QuestionAnswerer


def direct_answer_node(state: GraphState) -> GraphState:
    """
    Conversational fallback node.

    Delegates ALL semantic decisions to QuestionAnswerer.
    """
    answerer = QuestionAnswerer()
    model = state["runtime_config"].get("model")

    response = answerer.answer_question(
        query=state["user_query"],
        chat_history=state["chat_history"],
        language=state["detected_language"],
        sources=[],  # key signal
        model=model,
        is_moodle=False,
        course_id=None,
    )

    return {
        **state,
        "answer": response.content,
        "citations_markdown": response.content,
    }


def build_no_vectordb_graph() -> StateGraph:
    graph = StateGraph(GraphState)

    graph.add_node("detect_language_node", detect_language)
    graph.add_node("direct_answer_node", direct_answer_node)

    graph.add_edge(START, "detect_language_node")
    graph.add_edge("detect_language_node", "direct_answer_node")
    graph.add_edge("direct_answer_node", END)

    return graph.compile()