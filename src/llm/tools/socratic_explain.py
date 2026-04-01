from langfuse.decorators import observe

from src.llm.objects.LLMs import LLM
from src.llm.prompts.prompt_loader import load_prompt
from src.llm.streaming import StreamPhaseContext

# Load prompt once at module level
llm = LLM()
SOCRATIC_EXPLAIN_PROMPT = load_prompt("socratic_explain")

@observe(name="socratic_explain")
def socratic_explain(learning_objective: str,
                     user_query: str,
                     reranked_chunks: list,
                     chat_history: list,
                     number_given_hints: int,
                     attempt_count: int,
                     model: str) -> str:
    """
    Provides controlled explanation when Socratic method reaches its limit.
    
    Purpose:
    - Give clear, structured explanation of the concept
    - Reference student's prior attempts (what was correct/incorrect)
    - Use retrieved course content to ground explanation
    - Offer follow-up practice or move to reflection
    
    Triggers:
    - Explicit student request ("Gib mir einfach die Antwort")
    - Too many attempts/hints without progress
    
    Strategy:
    - Use reranked chunks to provide fact-based explanation
    - Acknowledge student's efforts and partial understanding
    - Provide structured, clear explanation
    - Offer practice opportunity (back to core) or conclude (reflection)
    
    Flow Transitions:
    - → "core": Offer practice with similar problem
    - → "reflection": If student satisfied or goal achieved
    
    Changes:
    - Returns a structured explanation grounded in retrieved content
    - Serves as the final core step before forced feedback
    
    Args:
        state: Current graph state with reranked chunks, chat_history, number_given_hints
        
    Returns:
        Updated state with explanation and routing decision
    """
    
    # Prepare context for LLM
    course_materials = "\n\n".join([
        f"[Material {i+1}]\n{chunk.text}"
        for i, chunk in enumerate(reranked_chunks)
    ]) if reranked_chunks else "No specific course materials retrieved."
    
    query_for_llm = f"""Learning Objective: {learning_objective}

Student's Current Response: {user_query}

Attempt Count: {attempt_count}
Number of given Hints: {number_given_hints}

Retrieved Course Materials:
{course_materials}"""
    
    # Generate explanation using LLM
    with StreamPhaseContext("final"):
        llm_response = llm.chat(
            query=query_for_llm,
            chat_history=chat_history,
            model=model,
            system_prompt=SOCRATIC_EXPLAIN_PROMPT
        )
    
    if llm_response.content is None:
        # Fallback if LLM fails
        explanation = (
            f"Lass mich {learning_objective} erklären:\n\n"
            "Leider konnte ich keine detaillierte Erklärung generieren. "
            "Bitte versuche es nochmal oder stelle eine spezifischere Frage."
        )
    else:
        explanation = llm_response.content.strip()
    
    return explanation