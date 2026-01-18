"""
Node wrapper for generating answers using QuestionAnswerer.
"""

from langfuse.decorators import observe

from src.llm.objects.LLMs import Models
from src.llm.state.models import GraphState, get_doc_as_textnodes

# Module-level singleton
_question_answerer_instance = None

def get_question_answerer():
    """Get or create singleton question answerer instance."""
    global _question_answerer_instance
    if _question_answerer_instance is None:
        from src.llm.objects.question_answerer import QuestionAnswerer
        _question_answerer_instance = QuestionAnswerer()
    return _question_answerer_instance


@observe()
def generate_answer(state: GraphState) -> dict:
    """
    Generates answer to user query using reranked sources.
    
    Changes:
    - Sets state.answer
    
    Args:
        state: Current graph state with user_query, chat_history, detected_language, reranked, and configs
        
    Returns:
        Updated state with generated answer
    """
    # Get singleton question answerer
    answerer = get_question_answerer()
    
    # Get variables from state (convert to LlamaIndex types)
    query = state["user_query"]
    chat_history = state.get("chat_history", [])
    language = state["detected_language"]
    sources = get_doc_as_textnodes(state, "reranked")
    model = state["runtime_config"]["model"]
    is_moodle = state["runtime_config"]["course_id"] is not None
    course_id = state["runtime_config"]["course_id"]
    
    # Generate answer
    response = answerer.answer_question(
        query=query,
        chat_history=chat_history,
        language=language,
        sources=sources,
        model=model,
        is_moodle=is_moodle,
        course_id=course_id
    )
    
    # Extract answer text
    return {"answer": response.content}