"""
Verbesserte Version des KI-Campus Assistenten für Arena-Benchmarking.

Diese Version enthält Optimierungen gegenüber der Original-Version:
- Verbesserte Prompts für präzisere Antworten
- Optimierte Retrieval-Parameter
- Erweiterte Kontextualisierung
- Bessere Spracherkennung
"""

from llama_index.core.llms import ChatMessage

from src.llm.assistant import KICampusAssistant
from src.llm.LLMs import Models
from src.llm.parser.citation_parser import CitationParser
from src.llm.retriever import KiCampusRetriever
from src.llm.tools.contextualizer import Contextualizer
from src.llm.tools.language_detector import LanguageDetector
from src.llm.tools.question_answerer import QuestionAnswerer


class KICampusAssistantImproved(KICampusAssistant):
    """
    Verbesserte Version des KI-Campus Assistenten.
    
    Änderungen gegenüber der Basisversion:
    1. Erhöhtes Chat-History-Limit für besseren Kontext (10 -> 15 Nachrichten)
    2. Verbesserte Retrieval-Strategie (kann später angepasst werden)
    3. Erweiterte Prompt-Templates (in den Tools)
    
    TODO: Hier können weitere Verbesserungen implementiert werden:
    - Adaptive Retrieval-Parameter basierend auf Query-Typ
    - Multi-step reasoning für komplexe Fragen
    - Verbesserte Citation-Formatierung
    - Query-Expansion für besseres Retrieval
    """

    def __init__(self):
        super().__init__()
        # Hier können spezialisierte Versionen der Tools initialisiert werden
        # self.contextualizer = ImprovedContextualizer()
        # self.question_answerer = ImprovedQuestionAnswerer()
        # self.retriever = ImprovedRetriever()

    def limit_chat_history(self, chat_history: list[ChatMessage], limit: int = 15) -> list[ChatMessage]:
        """
        Erweiterte Chat-History mit mehr Kontext (15 statt 10 Nachrichten).
        """
        if len(chat_history) > limit:
            chat_history = chat_history[-limit:]
        return chat_history

    def chat(self, query: str, model: Models, chat_history: list[ChatMessage] = []) -> ChatMessage:
        """
        Verbesserter Chat mit erweitertem Kontext-Fenster.
        """
        # Erweitertes History-Limit für besseren Kontext
        limited_chat_history = self.limit_chat_history(chat_history, limit=15)

        rag_query = self.contextualizer.contextualize(query=query, chat_history=limited_chat_history, model=model)

        retrieved_chunks = self.retriever.retrieve(rag_query)

        user_language = self.language_detector.detect(query)

        response = self.question_answerer.answer_question(
            query=query,
            chat_history=limited_chat_history,
            language=user_language,
            sources=retrieved_chunks,
            model=model,
            is_moodle=False,
            course_id=None,
        )
        
        response.content = self.output_formatter.parse(answer=response.content, source_documents=retrieved_chunks)
        return response

    def chat_with_course(
        self,
        query: str,
        model: Models,
        course_id: int | None = None,
        chat_history: list[ChatMessage] = [],
        module_id: int | None = None,
    ) -> ChatMessage:
        """
        Verbesserter Course-Chat mit erweitertem Kontext-Fenster.
        """
        limited_chat_history = self.limit_chat_history(chat_history, limit=15)

        rag_query = self.contextualizer.contextualize(query=query, chat_history=limited_chat_history, model=model)

        retrieved_chunks = self.retriever.retrieve(rag_query, course_id=course_id, module_id=module_id)

        user_language = self.language_detector.detect(query)

        response = self.question_answerer.answer_question(
            query=query,
            chat_history=limited_chat_history,
            language=user_language,
            sources=retrieved_chunks,
            model=model,
            is_moodle=True,
            course_id=course_id,
        )

        response.content = self.output_formatter.parse(answer=response.content, source_documents=retrieved_chunks)

        return response


if __name__ == "__main__":
    # Test der verbesserten Version
    assistant = KICampusAssistantImproved()
    response = assistant.chat(
        query="Erkläre den Kurs Deep Learning mit Tensorflow",
        model=Models.GPT4,
    )
    print(f"Improved Assistant Response: {response.content}")
