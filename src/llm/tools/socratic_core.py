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
from src.llm.tools.socratic_hinting import generate_hint_text
from src.llm.tools.socratic_reflection import generate_reflection_text
from src.llm.state.socratic_routing import reset_socratic_state

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
    chat_history = state["chat_history"]
    learning_objective = state["learning_objective"]
    attempt_count = state["attempt_count"]
    stuckness_score = state["stuckness_score"]
    hint_level = state["hint_level"]
    
    # Step 1: Retrieve relevant course content
    # This grounds the Socratic dialogue in actual course material
    # Annahme: Fragen sind spezifisch auf Kursinhalte bezogen --> simple_hop genügt
    state_after_retrieval = retrieve_chunks(state)
    
    # Step 2: Rerank retrieved chunks for relevance
    state_after_rerank = rerank_chunks(state_after_retrieval)
    
    # Increment attempt counter
    new_attempt_count = attempt_count + 1
    
    # Get model from state
    model = state["runtime_config"]["model"]
    
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
        # Student is stuck, provide hint INLINE
        next_mode = "core"  # Stay in core after hint
        
        # Increment hint level (max 3)
        new_hint_level = min(3, hint_level + 1)
        
        # Generate hint using helper function
        reranked_chunks = state_after_rerank["reranked"]
        response = generate_hint_text(
            hint_level=new_hint_level,
            learning_objective=learning_objective,
            user_query=user_query,
            reranked_chunks=reranked_chunks,
            chat_history=chat_history,
            model=model
        )
        
        # Reduce stuckness after providing hint
        new_stuckness_score = max(0.0, new_stuckness_score - 0.2)
        # Reset attempt counter
        new_attempt_count = 0
        
        # Check if we've given 3 hints and should escalate to explain
        contract = state.get("socratic_contract", {})
        if new_hint_level >= 3 and contract.get("allow_explain", False):
            next_mode = "explain"
            
    elif goal_achieved:
        # Student has reached understanding, provide reflection INLINE
        # Generate reflection using helper function
        student_model = state.get("student_model", {})
        response, _ = generate_reflection_text(
            learning_objective=learning_objective,
            student_model=student_model
        )
        
        # Reset all socratic state (session complete)
        socratic_reset = reset_socratic_state()
        
    else:
        # Continue Socratic dialogue
        next_mode = "core"
        
        # Generate LLM-based Socratic question using reranked course materials
        reranked_chunks = state_after_rerank["reranked"]
        
        # Prepare context for LLM
        # Format reranked chunks as course materials
        course_materials = "\n\n".join([
            f"[Material {i+1}]\n{chunk.text}"
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
    
    # Build return state
    result = {
        **state_after_rerank,  # Include retrieved and reranked chunks
        "attempt_count": new_attempt_count,
        "stuckness_score": new_stuckness_score,
        "goal_achieved": goal_achieved,
        "answer": response,
        "citations_markdown": None,  # Clear citations from previous requests
    }
    
    # Add hint_level if we gave a hint
    if 'new_hint_level' in locals():
        result["hint_level"] = new_hint_level
    
    # If reflection was done, reset all socratic state
    if 'socratic_reset' in locals():
        result.update(socratic_reset)
    else:
        # Normal flow: keep socratic_mode
        result["socratic_mode"] = next_mode
    
    return result
