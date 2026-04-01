"""
Node wrapper for contextualizing user query and routing to appropriate scenario.
"""

from langfuse.decorators import observe

from src.llm.state.models import GraphState, build_active_socratic_agent_state
from src.llm.state.socratic_routing import reset_socratic_state

# Module-level singleton
_contextualizer_instance = None

SOCRATIC_START_TRIGGERS = {
    "start socratic",
    "begin socratic",
    "enter socratic",
    "unterstütze mich beim lernen",
}

SOCRATIC_EXIT_TRIGGERS = {
    "exit",
    "quit",
    "stop",
    "stopp",
    "beende den lernmodus",
    "ich möchte aufhören",
}

SOCRATIC_EXIT_MESSAGE = "Du hast den Lernmodus verlassen. Wenn du weitere Fragen hast, stehe ich dir gerne zur Verfügung!"

def get_contextualizer():
    """Get or create singleton contextualizer instance."""
    global _contextualizer_instance
    if _contextualizer_instance is None:
        from src.llm.objects.contextualizer import Contextualizer
        _contextualizer_instance = Contextualizer()
    return _contextualizer_instance


@observe()
def contextualize_and_route(state: GraphState) -> dict:
    """
    Routes user query to appropriate scenario and contextualizes with chat history.
    
    Socratic Agent Handling:
    1. Check if socratic_agent.active
    2. If yes: Check if user wants to continue or exit
    3. If exit: reset agent state and return fixed exit answer
    4. If continue: keep mode=socratic and contextualize only in core phase
    
    Order: Route first (on original query), then contextualize.
    
    Changes:
    - Sets state["mode"] (routing decision based on original query)
    - Sets state["contextualized_query"] (contextualized with chat history)
    - Manages state["socratic_agent"] lifecycle
    
    Args:
        state: Current graph state with user_query, chat_history, config
        
    Returns:
        Updated state with mode and contextualized_query (see Changes)
    """

    # Get singleton contextualizer
    contextualizer = get_contextualizer()
    # Get necessary fields from state
    model = state["runtime_config"]["model"]
    user_query = state["user_query"]
    chat_history = state["chat_history"]
    socratic_agent = state.get("socratic_agent") or {}
    # Cleaned user response for entry/exit intent (socratic mode)
    response_clean = user_query.lower().strip()

    # Handle socratic agent if active
    if socratic_agent.get("active", False):
        # Start buzzword is treated as toggle when already inside socratic mode.
        wants_exit = response_clean in SOCRATIC_EXIT_TRIGGERS or response_clean in SOCRATIC_START_TRIGGERS

        if wants_exit:
            return {
                **reset_socratic_state(),
                "mode": "exit_complete",
                "answer": SOCRATIC_EXIT_MESSAGE,
            }

        contextualized_query = None
        if socratic_agent.get("phase") == "core":
            contextualized_query = contextualizer.contextualize_socratic(
                query=user_query,
                chat_history=chat_history,
                model=model,
                learning_objective=socratic_agent.get("learning_objective") or "",
            )

        return {
            "mode": "socratic",
            "contextualized_query": contextualized_query,
        }

    # Normal mode handling (no active socratic session)
    if response_clean in SOCRATIC_START_TRIGGERS:
        return {
            "mode": "socratic",
            "socratic_agent": build_active_socratic_agent_state(),
            "contextualized_query": None,
        }

    # Classify scenario based on original query
    mode = contextualizer.classify_scenario(query=user_query, model=model)

    # Contextualize query if needed
    if mode == "no_vectordb" or mode == "multi_hop":
        contextualized_query = None
    else:
        contextualized_query = contextualizer.contextualize(
            query=user_query,
            chat_history=chat_history,
            model=model,
        )

    return {
        "mode": mode,
        "contextualized_query": contextualized_query,
    }