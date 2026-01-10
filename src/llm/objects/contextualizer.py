from langfuse.decorators import observe
from llama_index.core.llms import ChatMessage

from src.llm.objects.LLMs import LLM, Models
from src.llm.prompts.prompt_loader import load_prompt

CONDENSE_QUESTION_PROMPT = load_prompt("contextualizer_prompt")


class Contextualizer:
    """Contextualizes a message based on the chat history, so that it can effectively used as input for RAG retrieval."""

    def __init__(self):
        self.llm = LLM()

    @observe()
    def contextualize(self, query: str, chat_history: list[ChatMessage], model: Models) -> str:
        """Contextualize a message based on the chat history, so that it can effectively used as input for RAG retrieval."""

        contextualized_question = self.llm.chat(
            query=query, chat_history=chat_history, model=model, system_prompt=CONDENSE_QUESTION_PROMPT
        )
        if contextualized_question.content is None:
            raise ValueError(
                f"Contextualized question is None. Please check the LLM implementation. Response: {contextualized_question}"
            )

        return contextualized_question.content
