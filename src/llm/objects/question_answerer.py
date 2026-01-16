import json
import sys

from langfuse.decorators import observe
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.schema import TextNode

from src.llm.objects.LLMs import LLM, Models
from src.llm.prompts.prompt_loader import load_prompt


# =============================
# User-facing messages
# =============================

ANSWER_SMALL_TALK = (
    "Ich bin der KI-Chatbot des KI-Campus. 😊 "
    "Ich kann keine persönlichen Gespräche führen, unterstütze dich aber gerne bei Fragen zu unseren Kursen."
)

ANSWER_OUT_OF_SCOPE = (
    "Zu diesem Thema kann ich leider keine Informationen bereitstellen. 🤔 "
    "Ich unterstütze dich gerne bei Fragen zu den Kursen des KI-Campus."
)

ANSWER_NOT_UNDERSTOOD_FIRST = (
    "Entschuldige, ich habe deine Frage nicht ganz verstanden. 🤔 "
    "Könntest du dein Problem bitte noch einmal etwas genauer erklären "
    "oder anders formulieren?"
)

ANSWER_NOT_UNDERSTOOD_SECOND_DRUPAL = (
    "Entschuldigung, ich habe deine Frage immer noch nicht verstanden. 📩 "
    "Bitte wende dich an unseren Support unter support@ki-campus.org."
)

ANSWER_NOT_UNDERSTOOD_SECOND_MOODLE = (
    "Es tut mir leid, aber ich konnte die benötigten Informationen im Kurs nicht finden. 📚\n"
    "Schau bitte im Kurs selbst nach:\n"
    "https://moodle.ki-campus.org/course/view.php?id={course_id}"
)


# =============================
# Prompts
# =============================

SHORT_SYSTEM_PROMPT = load_prompt("short_system_prompt")
SYSTEM_PROMPT = load_prompt("long_system_prompt")


CLASSIFIER_PROMPT_SOURCES_AVAILABLE = """
You are a classifier for the KI-Campus assistant.

Decide which ONE category the user input belongs to.

GIBBERISH:
- random characters or keyboard mashing
- unreadable or meaningless strings

SMALL_TALK:
- greetings
- casual conversation
- personal questions
- chit-chat
- asking about the assistant

OUT_OF_SCOPE:
- general knowledge
- everyday life questions
- school knowledge
- biology, astronomy, physics (unless explicitly about AI)
- topics unrelated to AI, learning AI, or KI-Campus

IN_SCOPE:
- any topic that could reasonably be part of a KI-Campus course
- foundational or advanced learning content
- technical, scientific, or mathematical topics used in courses
- concepts taught as prerequisites or core material
- explanations of terms, methods, or concepts from courses
- questions about KI-Campus courses, platform, or learning content

Rules:
- If the text is gibberish, choose GIBBERISH.
- If it is small talk, choose SMALL_TALK.
- If it is not clearly about AI or KI-Campus, choose OUT_OF_SCOPE.
- Otherwise choose IN_SCOPE.

Answer exactly ONE word:
GIBBERISH
SMALL_TALK
OUT_OF_SCOPE
IN_SCOPE
""".strip()


CLASSIFIER_PROMPT_SOURCES_NOT_AVAILABLE = """
You are a classifier and gatekeeper for the KI-Campus assistant.

Decide which ONE category the user input belongs to.

GIBBERISH:
- random characters or keyboard mashing
- unreadable or meaningless strings

SMALL_TALK:
- greetings
- casual conversation
- personal questions
- chit-chat
- meta questions like "can you help me?"

OUT_OF_SCOPE:
- general knowledge
- everyday life questions
- school knowledge
- biology, astronomy, physics
- anything NOT related to AI learning or KI-Campus

IN_SCOPE_ANSWER:
- any topic that could reasonably be part of a KI-Campus course
- foundational or advanced learning content
- technical, scientific, or mathematical concepts
- explanations of methods, terms, or concepts used in courses
- questions about KI-Campus courses or the learning platform
- AND the question can be answered without requiring specific course materials

IN_SCOPE_NO_ANSWER:
- AI or KI-Campus related
- BUT cannot be answered reliably without course sources

Rules:
- If gibberish → GIBBERISH
- If small talk → SMALL_TALK
- If unrelated → OUT_OF_SCOPE
- If AI-related and answerable without sources → IN_SCOPE_ANSWER
- Otherwise → IN_SCOPE_NO_ANSWER

Answer exactly ONE word:
GIBBERISH
SMALL_TALK
OUT_OF_SCOPE
IN_SCOPE_ANSWER
IN_SCOPE_NO_ANSWER
""".strip()


USER_QUERY_WITH_SOURCES_PROMPT = """
[doc{index}]
Content: {content}
Metadata: {metadata}
""".strip()


# =============================
# Helper functions
# =============================

def format_sources(sources: list[TextNode], max_length: int = 8000) -> str:
    sources_text = ""
    for i, source in enumerate(sources):
        entry = USER_QUERY_WITH_SOURCES_PROMPT.format(
            index=i + 1,
            content=source.get_text(),
            metadata=source.metadata,
        )
        if len(sources_text) + len(entry) > max_length:
            break
        sources_text += entry + "\n"

    return "<SOURCES>:\n" + sources_text.strip()


def previous_not_understood(chat_history) -> bool:
    for msg in reversed(chat_history or []):
        if msg.role == MessageRole.ASSISTANT:
            return msg.content == ANSWER_NOT_UNDERSTOOD_FIRST
    return False


# =============================
# Core class
# =============================

class QuestionAnswerer:
    def __init__(self) -> None:
        self.llm = LLM()

    @observe()
    def answer_question(
        self,
        query: str,
        chat_history: list[ChatMessage],
        sources: list[TextNode],
        model: Models,
        language: str,
        is_moodle: bool,
        course_id: int,
    ) -> ChatMessage:

        was_not_understood_before = previous_not_understood(chat_history)

        classifier_prompt = (
            CLASSIFIER_PROMPT_SOURCES_AVAILABLE
            if sources
            else CLASSIFIER_PROMPT_SOURCES_NOT_AVAILABLE
        )

        classification = self.llm.chat(
            query=query,
            chat_history=[],
            model=model,
            system_prompt=classifier_prompt,
        )

        label = classification.content.strip().upper()

        # =============================
        # Classification handling
        # =============================

        if label == "GIBBERISH":
            return ChatMessage(
                role=MessageRole.ASSISTANT,
                content=(
                    ANSWER_NOT_UNDERSTOOD_SECOND_MOODLE.format(course_id=course_id)
                    if was_not_understood_before and is_moodle and course_id
                    else ANSWER_NOT_UNDERSTOOD_SECOND_DRUPAL
                    if was_not_understood_before
                    else ANSWER_NOT_UNDERSTOOD_FIRST
                ),
            )

        if label == "SMALL_TALK":
            return ChatMessage(
                role=MessageRole.ASSISTANT,
                content=ANSWER_SMALL_TALK,
            )

        if label in {"OUT_OF_SCOPE", "IN_SCOPE_NO_ANSWER"}:
            return ChatMessage(
                role=MessageRole.ASSISTANT,
                content=ANSWER_OUT_OF_SCOPE,
            )

        # =============================
        # IN_SCOPE / IN_SCOPE_ANSWER
        # =============================

        system_prompt = (
            SHORT_SYSTEM_PROMPT.format(language=language)
            if model != Models.GPT4
            else SYSTEM_PROMPT.format(language=language)
        )

        prompted_query = query

        if sources:
            formatted_sources = format_sources(
                sources,
                max_length=8000 if model != Models.GPT4 else sys.maxsize,
            )
            prompted_query = f"<QUERY>:\n{query}\n---\n\n{formatted_sources}"

        response = self.llm.chat(
            query=prompted_query,
            chat_history=chat_history,
            model=model,
            system_prompt=system_prompt,
        )

        # =============================
        # Optional JSON cleanup
        # =============================

        try:
            cleaned = response.content.replace("json\n", "").replace("\n", "")
            response_json = json.loads(cleaned)
            response.content = response_json["answer"]
        except Exception:
            pass

        if response.content == "NO ANSWER FOUND":
            response.content = (
                ANSWER_NOT_UNDERSTOOD_FIRST
                if not was_not_understood_before
                else (
                    ANSWER_NOT_UNDERSTOOD_SECOND_MOODLE.format(course_id=course_id)
                    if is_moodle and course_id
                    else ANSWER_NOT_UNDERSTOOD_SECOND_DRUPAL
                )
            )

        return response