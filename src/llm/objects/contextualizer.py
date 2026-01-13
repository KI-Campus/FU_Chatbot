from langfuse.decorators import observe
from llama_index.core.llms import ChatMessage

from src.llm.objects.LLMs import LLM, Models
from src.llm.prompts.prompt_loader import load_prompt

CONDENSE_QUESTION_PROMPT = load_prompt("contextualizer_prompt")
CONDENSE_SOCRATIC_PROMPT = load_prompt("contextualizer_socratic_prompt")


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

    @observe()
    def contextualize_socratic(self, query: str, chat_history: list[ChatMessage], model: Models, learning_objective: str = "") -> str:
        """
        Contextualize a message for socratic core mode retrieval.
        
        Uses contextualizer_socratic_prompt.txt to create a retrieval query
        that considers the learning objective and socratic dialogue context.
        
        Args:
            query: Current user query/response
            chat_history: Previous conversation messages
            model: LLM model to use
            learning_objective: The identified learning goal
            
        Returns:
            Contextualized query optimized for socratic retrieval
        """
        # Prepend learning objective to query if available
        if learning_objective:
            query_with_objective = f"Learning Goal: {learning_objective}\n\nCurrent Response: {query}"
        else:
            query_with_objective = query
        
        contextualized_question = self.llm.chat(
            query=query_with_objective,
            chat_history=chat_history,
            model=model,
            system_prompt=CONDENSE_SOCRATIC_PROMPT
        )
        
        if contextualized_question.content is None:
            raise ValueError(
                f"Contextualized socratic question is None. Please check the LLM implementation. Response: {contextualized_question}"
            )
        
        return contextualized_question.content