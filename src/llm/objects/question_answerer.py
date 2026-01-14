import json
import sys
import re

from langfuse.decorators import observe
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.schema import TextNode

from src.llm.objects.LLMs import LLM, Models
from src.llm.prompts.prompt_loader import load_prompt


# =============================
# User-facing messages
# =============================

ANSWER_SMALL_TALK = (
    "Ich bin der KI-Chatbot des KI-Campus 😊 "
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

SMALL_TALK_CLASSIFIER_PROMPT = """
You are an intent classifier.

Decide whether the user message is SMALL TALK.

SMALL TALK includes:
- greetings
- casual conversation
- weather talk
- personal questions
- chit-chat
- asking about the assistant
- meta questions like "can you help me?"

IMPORTANT:
- If the message is random characters, nonsense, or unreadable, it is NOT small talk.

Answer exactly:
YES  (if small talk)
NO   (otherwise)
""".strip()

SCOPE_CLASSIFIER_PROMPT = """
You are a scope classifier for the KI-Campus assistant.

Decide whether the user question is IN SCOPE for KI-Campus course-related support.

IN SCOPE includes:
- AI, Machine Learning, Deep Learning, Data Science, NLP, ethics of AI, AI basics
- questions about learning, courses, KI-Campus content

OUT OF SCOPE includes:
- unrelated general knowledge topics (e.g., astronomy like "stars", sports, celebrities)
- everyday unrelated questions

Answer exactly:
IN_SCOPE
OUT_OF_SCOPE
""".strip()

GENERAL_KICAMPUS_PROMPT = """
You are the KI-Campus assistant.

If the user asks about AI / Machine Learning / Deep Learning / KI basics, answer clearly and helpfully.
Keep it short and educational.

If the user asks something unrelated to AI learning or KI-Campus, answer exactly:
NO ANSWER FOUND
""".strip()

USER_QUERY_WITH_SOURCES_PROMPT = """
[doc{index}]
Content: {content}
Metadata: {metadata}
""".strip()


# =============================
# Helpers
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


def looks_like_gibberish(text: str) -> bool:
    t = text.strip().lower()

    if len(t) < 4:
        return True

    if " " not in t and len(t) > 12:
        return True

    letters = re.findall(r"[a-zäöü]", t)
    if not letters:
        return True

    vowels = re.findall(r"[aeiouäöü]", t)
    if len(vowels) / len(letters) < 0.2:
        return True

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

        # -------------------------------------------------
        # 0) Gibberish first (so it won't be mistaken as small talk)
        # -------------------------------------------------
        if looks_like_gibberish(query):
            return ChatMessage(
                role=MessageRole.ASSISTANT,
                content=ANSWER_NOT_UNDERSTOOD_FIRST,
            )

        # -------------------------------------------------
        # 1) SMALL TALK → immediate response (LLM classifier)
        # -------------------------------------------------
        st = self.llm.chat(
            query=query,
            chat_history=[],
            model=model,
            system_prompt=SMALL_TALK_CLASSIFIER_PROMPT,
        )
        if st.content.strip().upper() == "YES":
            return ChatMessage(
                role=MessageRole.ASSISTANT,
                content=ANSWER_SMALL_TALK,
            )

        # -------------------------------------------------
        # 2) If NO SOURCES: decide IN_SCOPE vs OUT_OF_SCOPE and answer accordingly
        # -------------------------------------------------
        if not sources:
            scope = self.llm.chat(
                query=query,
                chat_history=[],
                model=model,
                system_prompt=SCOPE_CLASSIFIER_PROMPT,
            )

            if scope.content.strip().upper() == "OUT_OF_SCOPE":
                return ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content=ANSWER_OUT_OF_SCOPE,
                )

            # IN_SCOPE -> answer from general knowledge (no retrieval)
            general = self.llm.chat(
                query=query,
                chat_history=chat_history,
                model=model,
                system_prompt=GENERAL_KICAMPUS_PROMPT,
            )

            # Keep old safety-net behavior
            if general.content.strip() == "NO ANSWER FOUND":
                return ChatMessage(
                    role=MessageRole.ASSISTANT,
                    content=ANSWER_OUT_OF_SCOPE,
                )

            return general

        # -------------------------------------------------
        # 3) Normal answering with sources (RAG path)
        # -------------------------------------------------
        system_prompt = (
            SHORT_SYSTEM_PROMPT.format(language=language)
            if model != Models.GPT4
            else SYSTEM_PROMPT.format(language=language)
        )

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

        # Best-effort JSON parsing
        try:
            cleaned = response.content.replace("json\n", "").replace("\n", "")
            response_json = json.loads(cleaned)
            response.content = response_json["answer"]
        except Exception:
            pass

        previous_not_understood = False
        for msg in reversed(chat_history or []):
            if msg.role == MessageRole.ASSISTANT:
                previous_not_understood = (msg.content == ANSWER_NOT_UNDERSTOOD_FIRST)
                break

        # -------------------------------------------------
        # 4) NO ANSWER FOUND handling
        # -------------------------------------------------
        if response.content == "NO ANSWER FOUND":
            if not previous_not_understood:
                response.content = ANSWER_NOT_UNDERSTOOD_FIRST
            else:
                response.content = (
                    ANSWER_NOT_UNDERSTOOD_SECOND_MOODLE.format(course_id=course_id)
                    if is_moodle and course_id
                    else ANSWER_NOT_UNDERSTOOD_SECOND_DRUPAL
                )

        if response.content == "NO ANSWER FOUND":
            response.content = ANSWER_NOT_UNDERSTOOD_FIRST

        return response