from langfuse.decorators import observe
from lingua import Language, LanguageDetectorBuilder

from src.api.models.serializable_chat_message import SerializableChatMessage


class LanguageDetector:
    def __init__(self):
        languages = [
            Language.ENGLISH,
            Language.GERMAN,
        ]
        self.detector = LanguageDetectorBuilder.from_languages(*languages).build()

    @observe()
    def detect(self, query: str, chat_history: list[SerializableChatMessage] | None = None) -> str:
        """Detect language from current query and chat history context.
        
        Uses the full conversation history to determine the dominant language,
        preventing incorrect language switches when users use short queries like
        'Tell me more' or 'Was ist das?'
        
        Args:
            query: The current user query
            chat_history: Previous messages in the conversation (optional)
            
        Returns:
            Detected language name (e.g., 'German', 'English')
        """
        # Combine recent history with current query for better detection
        text_to_analyze = query
        
        if chat_history:
            # Take last 3 messages for context (more recent = more relevant)
            recent_messages = chat_history[-3:] if len(chat_history) > 3 else chat_history
            history_text = " ".join([msg.content for msg in recent_messages if msg.content])
            # Prioritize current query but include history for context
            text_to_analyze = f"{query} {history_text}"
        
        language = self.detector.detect_language_of(text_to_analyze)
        if language is None:
            return "German"
        camelcase_name = language.name.capitalize()
        
        return camelcase_name
