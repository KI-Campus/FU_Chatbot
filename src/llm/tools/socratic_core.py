"""
Socratic Core Node - Main Socratic questioning loop.

Heart of the socratic workflow: Asks guiding questions, tracks progress, manages transitions.
Uses Retrieval to ground questions in actual course content.
"""

from langfuse.decorators import observe

from src.llm.state.models import GraphState
from src.llm.tools.retrieve import retrieve_chunks
from src.llm.tools.rerank import rerank_chunks
from src.llm.state.socratic_stuckness_goal_achievement import assess_stuckness_and_goal
from src.llm.objects.LLMs import LLM
from src.llm.prompts.prompt_loader import load_prompt

# Load prompt once at module level
SOCRATIC_CORE_PROMPT = load_prompt("socratic_core")


@observe()
def socratic_core(state: GraphState) -> GraphState:
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
    - Escalate to "hinting" if stuck (stuckness > 0.7 or attempts > 3)
    - Move to "reflection" if goal achieved
    
    Flow Transitions:
    - → "core" (loop): Student progressing, continue Socratic dialogue
    - → "hinting": Student stuck, needs graduated hints
    - → "reflection": Goal achieved, consolidate learning
    
    Changes:
    - Sets retrieved and reranked chunks (for grounding in course content)
    - Increments attempt_count
    - Updates stuckness_score
    - Updates goal_achieved (if student shows understanding)
    - Sets socratic_mode for next step
    - Sets answer with Socratic question or transition message
    
    Args:
        state: Current graph state with user_query, chat_history, learning_objective
        
    Returns:
        Updated state with next Socratic question and routing decision
    """
    
    user_query = state["user_query"]
    chat_history = state.get("chat_history", [])
    learning_objective = state.get("learning_objective", "")
    attempt_count = state.get("attempt_count", 0)
    stuckness_score = state.get("stuckness_score", 0.0)
    hint_level = state.get("hint_level", 0)
    
    # Step 1: Retrieve relevant course content
    # This grounds the Socratic dialogue in actual course material
    # Annahme: Fragen sind spezifisch auf Kursinhalte bezogen --> simple_hop genügt
    state_after_retrieval = retrieve_chunks(state)
    
    # Step 2: Rerank retrieved chunks for relevance
    state_after_rerank = rerank_chunks(state_after_retrieval)
    
    # Increment attempt counter
    new_attempt_count = attempt_count + 1
    
    # Get model from state (fallback to default)
    model = state.get("model", "gpt-4o-mini")
    
    # LLM-based assessment of stuckness and goal achievement
    new_stuckness_score, goal_achieved = assess_stuckness_and_goal(
        user_query=user_query,
        chat_history=chat_history,
        learning_objective=learning_objective,
        attempt_count=new_attempt_count,
        current_stuckness=stuckness_score,
        model=model
    )
    
    # Decide next mode based on stuckness and attempts
    if new_stuckness_score > 0.7 or new_attempt_count > 3:
        # Student is stuck, escalate to hinting
        next_mode = "hinting"
        response = (
            "Ich merke, dass das eine Herausforderung ist. "
            "Lass mich dir einen Hinweis geben, der dich weiterbringen könnte..."
        )
    elif goal_achieved:
        # Student has reached understanding, move to reflection
        next_mode = "reflection"
        response = (
            "Sehr gut! Du hast das Konzept erfasst. "
            "Lass uns kurz reflektieren, was du gelernt hast..."
        )
    else:
        # Continue Socratic dialogue
        next_mode = "core"
        
        # Generate LLM-based Socratic question using reranked course materials
        reranked_chunks = state_after_rerank.get("reranked", [])
        
        # Prepare context for LLM
        # Format reranked chunks as course materials
        course_materials = "\n\n".join([
            f"[Material {i+1}]\n{chunk.page_content}"
            for i, chunk in enumerate(reranked_chunks[:3])  # Top 3 chunks
        ]) if reranked_chunks else "No specific course materials retrieved."
        
        query_for_llm = f"""Learning Objective: {learning_objective}

Student's Current Response: {user_query}

Attempt Count: {new_attempt_count}
Stuckness Score: {new_stuckness_score}

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
    
    return {
        **state_after_rerank,  # Include retrieved and reranked chunks
        "attempt_count": new_attempt_count,
        "stuckness_score": new_stuckness_score,
        "goal_achieved": goal_achieved,
        "socratic_mode": next_mode,
        "answer": response,
    }
