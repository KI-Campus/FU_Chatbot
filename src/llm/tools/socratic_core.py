"""
Socratic Core Node - Main Socratic questioning loop.

Heart of the socratic workflow: Asks guiding questions, tracks progress, manages transitions.
Uses Retrieval to ground questions in actual course content.
"""

from langfuse.decorators import observe

from src.llm.state.models import GraphState
from src.llm.objects.LLMs import LLM
from src.llm.prompts.prompt_loader import load_prompt
from src.llm.tools.socratic_hinting import generate_hint_text
from src.llm.tools.socratic_reflection import generate_reflection_text
from src.llm.state.socratic_routing import evaluate_user_response, answer_and_reset_socratic_state
from src.llm.tools.socratic_explain import socratic_explain

# Load prompt once at module level
SOCRATIC_CORE_PROMPT = load_prompt("socratic_core")


@observe(name="socratic_core")
def socratic_core(state: GraphState) -> dict:
    """
    Core Socratic dialogue: Ask one guiding question per turn, never give direct answer.
    
    Purpose:
    - Retrieve relevant course content to ground dialogue
    - Analyze student's response from previous turn
    - Assess understanding and detect stuckness
    - Ask targeted Socratic question to guide toward learning objective
    - Decide on next step (continue loop, escalate to hinting, or move to reflection)
    
    Strategy:
    - Retrieve + rerank course content based on contextualized query
    - Increment attempt counter with each turn
    - Calculate stuckness based on attempts and response quality
    - Loop back to "core" if student is progressing
    - Escalate to "hinting" if stuck
    - Move to "reflection" if goal achieved
    
    Flow Transitions:
    - → "core" (loop): Student progressing, continue Socratic dialogue
    - → "hinting": Student stuck, needs graduated hints
    - → "reflection": Goal achieved, consolidate learning
    
    Args:
        state: Current graph state with user_query, chat_history, learning_objective
        
    Returns:
        Updated state with next Socratic question and routing decision
    """
    
    # Get necessary data from state
    user_query = state["user_query"]
    chat_history = state["chat_history"]
    learning_objective = state["learning_objective"]
    attempt_count = state["attempt_count"]
    number_given_hints = state["number_given_hints"]
    model = state["runtime_config"]["model"]
    reranked = state["reranked"]
    
    # Increment attempt counter
    new_attempt_count = attempt_count + 1
    
    # LLM-based assessment to determine mode after 2 given hints we explain directly
    if number_given_hints > 2:
        mode = "EXPLAIN"
    else:
        mode = evaluate_user_response(
            user_query=user_query,
            chat_history=chat_history,
            learning_objective=learning_objective,
            attempt_count=new_attempt_count,
            model=model
        )
    
    # Handle different modes
    if mode == "EXPLAIN":
        # Reset socratic state --> student can decide whether he wants to continue or not
        next_mode = "diagnose"

        # Generate explanation using helper function
        response = socratic_explain(
            learning_objective=learning_objective,
            user_query=user_query,
            reranked_chunks=reranked,
            chat_history=chat_history,
            attempt_count=new_attempt_count,
            number_given_hints=number_given_hints,
            model=model
        )

        return answer_and_reset_socratic_state(next_mode, response)

    elif mode == "HINT":
        # Student is stuck, provide hint inline
        next_mode = "core"  # Stay in core after hint
        
        # Increment number of hints given
        new_number_given_hints = number_given_hints + 1
        
        # Generate hint using helper function (pass total number of hints)
        response = generate_hint_text(
            learning_objective=learning_objective,
            user_query=user_query,
            reranked_chunks=reranked,
            chat_history=chat_history,
            number_given_hints=new_number_given_hints,
            model=model
        )

        # Update state with hint
        return {
            "socratic_mode": next_mode,
            "attempt_count": new_attempt_count,
            "number_given_hints": new_number_given_hints,
            "answer": response
        }
            
    elif mode == "REFLECT":
        # Reset socratic state --> student can decide whether he wants to continue or not
        next_mode = "diagnose"

        # Student has reached understanding, provide reflection inline
        # Generate reflection using helper function
        response = generate_reflection_text(learning_objective=learning_objective)
        
        # Reset all socratic state (session complete)
        return answer_and_reset_socratic_state(next_mode, response)
        
    else:  # mode == "CONTINUE"
        # Continue Socratic dialogue
        next_mode = "core"
        
        # Generate LLM-based Socratic question using reranked course materials
        response = generate_socratic_question(
            learning_objective=learning_objective,
            user_query=user_query,
            reranked=reranked,
            chat_history=chat_history,
            new_attempt_count=new_attempt_count,
            model=model
        )
    
    # Build return dict
        # Build return state
    result = {
        "socratic_mode": next_mode,
        "attempt_count": new_attempt_count,
        "answer": response
    }

    return result

@observe(name="socratic_question_generation")
def generate_socratic_question(learning_objective: str,
                     user_query: str,
                     reranked: list,
                     chat_history: list,
                     new_attempt_count: int,
                     model: str) -> str:
    """
    Generates the next Socratic question to ask the student.
    Args:
        learning_objective: The learning goal
        user_query: Student's current response
        reranked: Retrieved and reranked course materials
        chat_history: Conversation history
        new_attempt_count: Updated total attempt count
        model: LLM model to use
    Returns:
        str: The generated Socratic question
    """
    course_materials = "\n\n".join([
        f"[Material {i+1}]\n{chunk.text}"
        for i, chunk in enumerate(reranked)
        ]) if reranked else "No specific course materials retrieved."
        
    query_for_llm = f"""Learning Objective: {learning_objective}

Student's Current Response: {user_query}

Attempt Count: {new_attempt_count}

Retrieved Course Materials:
{course_materials}"""
        
    # Call LLM to generate Socratic question
    _llm = LLM()
    llm_response = _llm.chat(
        query=query_for_llm,
        chat_history=chat_history,
        model=model,
        system_prompt=SOCRATIC_CORE_PROMPT
        )
        
    if llm_response.content is None:
        # Fallback if LLM fails
        response = "Kannst du deine Überlegung genauer erklären?"
    else:
        response = llm_response.content.strip()
    
    return response