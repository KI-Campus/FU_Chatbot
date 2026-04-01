"""
Socratic Question Tool - Generates the next guiding question.
"""

from langfuse.decorators import observe

from src.llm.objects.LLMs import LLM
from src.llm.prompts.prompt_loader import load_prompt
from src.llm.streaming import StreamPhaseContext

SOCRATIC_CORE_PROMPT = load_prompt("socratic_core")


@observe(name="socratic_question")
def generate_socratic_question(
    learning_objective: str,
    user_query: str,
    reranked: list,
    chat_history: list,
    new_attempt_count: int,
    model: str,
) -> str:
    """Generate the next Socratic guiding question."""
    course_materials = (
        "\n\n".join([f"[Material {i + 1}]\n{chunk.text}" for i, chunk in enumerate(reranked)])
        if reranked
        else "No specific course materials retrieved."
    )

    query_for_llm = f"""Learning Objective: {learning_objective}

Student's Current Response: {user_query}

Attempt Count: {new_attempt_count}

Retrieved Course Materials:
{course_materials}"""

    llm = LLM()
    with StreamPhaseContext("final"):
        llm_response = llm.chat(
            query=query_for_llm,
            chat_history=chat_history,
            model=model,
            system_prompt=SOCRATIC_CORE_PROMPT,
        )

    if llm_response.content is None:
        return "Kannst du deine Überlegung genauer erklären?"

    return llm_response.content.strip()
