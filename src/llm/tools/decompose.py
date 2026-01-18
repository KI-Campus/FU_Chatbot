"""
Node for decomposing complex queries into sub-queries (Multi-Hop).
"""

import json
from langfuse.decorators import observe

from src.llm.objects.LLMs import LLM
from src.llm.state.models import GraphState, get_chat_history_as_messages
from src.llm.prompts.prompt_loader import load_prompt

# Load prompt
DECOMPOSE_PROMPT = load_prompt("decompose_prompt")

# Initialize LLM instance at module level
_llm = LLM()


@observe()
def decompose_query(state: GraphState) -> dict:
    """
    Decomposes complex query into multiple sub-queries for multi-hop retrieval.
    
    Each sub-query is self-contained and can be processed independently
    through a simple_hop retrieval flow.
    
    Changes:
    - Sets state["sub_queries"] (list of self-contained questions)
    
    Args:
        state: Current graph state with contextualized_query and runtime_config
        
    Returns:
        Updated state with sub_queries
    """
    # Extract model from runtime_config
    model = state["runtime_config"]["model"]
    query = state["user_query"]
    
    # Call LLM to decompose query
    response = _llm.chat(
        query=query,
        chat_history=get_chat_history_as_messages(state),
        model=model,
        system_prompt=DECOMPOSE_PROMPT
    )
    
    # Parse JSON response
    try:
        sub_queries = json.loads(response.content)
        if not isinstance(sub_queries, list) or len(sub_queries) == 0:
            # Fallback: use original query
            sub_queries = [query]
    except (json.JSONDecodeError, ValueError):
        # Fallback: use original query
        sub_queries = [query]
    
    return {"sub_queries": sub_queries}