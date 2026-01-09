"""
Node wrapper for generating answers using QuestionAnswerer.
"""

from langfuse.decorators import observe

from llm.objects.question_answerer import QuestionAnswerer
from llm.objects.LLMs import Models
from llm.state.models import GraphState


@observe()
def generate_answer(state: GraphState) -> GraphState:
    """
    Generates answer to user query using reranked sources.
    
    Changes:
    - Sets state.answer
    
    Args:
        state: Current graph state with user_query, chat_history, detected_language, reranked, and configs
        
    Returns:
        Updated state with generated answer
    """
    answerer = QuestionAnswerer()
    
    # Extract runtime config (from frontend)
    model = state.runtime_config.get("model", Models.GPT_4O_MINI)
    is_moodle = state.runtime_config.get("course_id") is not None
    course_id = state.runtime_config.get("course_id")
    
    # Generate answer (reranked already contains TextNodes)
    response = answerer.answer_question(
        query=state.user_query,
        chat_history=state.chat_history,
        language=state.detected_language,
        sources=state.reranked,
        model=model,
        is_moodle=is_moodle,
        course_id=course_id
    )
    
    # Extract answer text
    state.answer = response.content
    
    return state