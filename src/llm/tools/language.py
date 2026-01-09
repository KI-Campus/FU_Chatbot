"""
Node wrapper for detecting user's language.
"""

from langfuse.decorators import observe

from llm.objects.language_detector import LanguageDetector
from llm.state.models import GraphState


@observe()
def detect_language(state: GraphState) -> GraphState:
    """
    Detects the language of the user's query.
    
    Changes:
    - Sets state.detected_language
    
    Args:
        state: Current graph state with user_query and chat_history
        
    Returns:
        Updated state with detected_language
    """
    detector = LanguageDetector()
    
    language = detector.detect(
        query=state.user_query,
        chat_history=state.chat_history
    )
    
    state.detected_language = language
    
    return state