"""
Node wrapper for detecting user's language.
"""

from langfuse.decorators import observe

from src.llm.state.models import GraphState

# Module-level singleton
_language_detector_instance = None

def get_language_detector():
    """Get or create singleton language detector instance."""
    global _language_detector_instance
    if _language_detector_instance is None:
        from src.llm.objects.language_detector import LanguageDetector
        _language_detector_instance = LanguageDetector()
    return _language_detector_instance


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
    # Get singleton language detector
    detector = get_language_detector()

    # Get necessary variables from state
    query = state["user_query"]
    chat_history = state["chat_history"]
    
    language = detector.detect(
        query=query,
        chat_history=chat_history
    )
    
    return {"detected_language": language}