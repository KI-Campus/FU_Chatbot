from langfuse.decorators import observe

from src.llm.objects.LLMs import LLM
from src.llm.prompts.prompt_loader import load_prompt

# Load prompt once at module level
SOCRATIC_HINTING_PROMPT = load_prompt("socratic_hinting")

@observe(name="socratic_hinting")
def generate_hint_text(
    learning_objective: str,
    number_given_hints: int,
    user_query: str,
    reranked_chunks: list,
    chat_history: list,
    model: str
) -> str:
    """
    Helper function to generate a hint based on how many hints have been given.
    
    Args:
        learning_objective: The learning goal
        number_given_hints: Total number of hints given so far
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
Number of Hints Given: {number_given_hints}

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
        return "💡 **Hinweis:** Denke nochmal über die Grundkonzepte nach."
    else:
        return llm_response.content.strip()