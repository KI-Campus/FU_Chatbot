from src.llm.objects.LLMs import LLM
from src.llm.prompts.prompt_loader import load_prompt

# Load prompt once at module level
llm = LLM()
SOCRATIC_EXPLAIN_PROMPT = load_prompt("socratic_explain")

def socratic_explain(learning_objective: str,
                     user_query: str,
                     reranked_chunks: list,
                     chat_history: list,
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
    - hint_level == 3 AND contract.allow_explain == True
    - Explicit student request ("Gib mir einfach die Antwort")
    - Fail-policy: Too many attempts without progress
    
    Strategy:
    - Use reranked chunks to provide fact-based explanation
    - Acknowledge student's efforts and partial understanding
    - Provide structured, clear explanation
    - Offer practice opportunity (back to core) or conclude (reflection)
    
    Flow Transitions:
    - → "core": Offer practice with similar problem
    - → "reflection": If student satisfied or goal achieved
    
    Changes:
    - Sets answer with structured explanation
    - Updates student_model (marks topic as explained)
    - Resets hint_level to 0 (for potential practice round)
    - Sets socratic_mode for next step
    
    Args:
        state: Current graph state with reranked chunks, chat_history
        
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

Retrieved Course Materials:
{course_materials}"""
    
    # Generate explanation using LLM
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
    
    # Add closing text encouraging continuation
    closing_text = "\nFalls du weiterhin im Lernmodus bleiben möchtest, lasse mich wissen, bei welchem Thema ich dir weiterhin helfen kann! Andernfalls verlasse den Lernmodus mit 'quit'."
    full_response = explanation + closing_text
    
    return full_response