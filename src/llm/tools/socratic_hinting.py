"""
Socratic Hinting Node - Provides graduated hints (levels 1-3).

Escalates support when student is stuck, using course content for contextual hints.
"""

from langfuse.decorators import observe

from src.llm.state.models import GraphState, get_chat_history_as_messages
from src.llm.objects.LLMs import LLM
from src.llm.prompts.prompt_loader import load_prompt

# Load prompt once at module level
SOCRATIC_HINTING_PROMPT = load_prompt("socratic_hinting")


def generate_hint_text(
    hint_level: int,
    learning_objective: str,
    mastery_level: str,
    user_query: str,
    reranked_chunks: list,
    chat_history: list,
    model: str
) -> str:
    """
    Helper function to generate a hint based on current level.
    
    Args:
        hint_level: Current hint level (1-3)
        learning_objective: The learning goal
        mastery_level: Current mastery level of the student
        user_query: Student's current response
        reranked_chunks: Retrieved course materials
        chat_history: Conversation history
        model: LLM model to use
        
    Returns:
        Generated hint text
    """
    # Prepare context for LLM
    course_materials = "\n\n".join([
        f"[Material {i+1}]\n{chunk.text}"
        for i, chunk in enumerate(reranked_chunks[:3])
    ]) if reranked_chunks else "No specific course materials retrieved."
    
    query_for_llm = f"""Learning Objective: {learning_objective}
Mastery Level: {mastery_level}
Hint Level: {hint_level}

Student's Current Response: {user_query}

Retrieved Course Materials:
{course_materials}"""
    
    # Generate hint using LLM
    _llm = LLM()
    llm_response = _llm.chat(
        query=query_for_llm,
        chat_history=chat_history,
        model=model,
        system_prompt=SOCRATIC_HINTING_PROMPT
    )
    
    if llm_response.content is None:
        # Fallback if LLM fails
        return f"💡 **Hinweis {hint_level}:** Denke nochmal über die Grundkonzepte nach."
    else:
        return llm_response.content.strip()