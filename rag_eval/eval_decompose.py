"""
Node for decomposing complex queries into sub-queries (Multi-Hop).
"""

import json
from typing import List
from langfuse.decorators import observe

from src.llm.objects.LLMs import LLM, Models
from src.llm.prompts.prompt_loader import load_prompt

# Load prompt
DECOMPOSE_PROMPT = load_prompt("decompose_prompt")

# Initialize LLM instance at module level
_llm = LLM()


@observe()
def decompose_query_eval(model: Models, query: str) -> List[str]:
    """
    Decomposes complex query into multiple sub-queries for multi-hop retrieval.
    
    Each sub-query is self-contained and can be processed independently
    through a simple_hop retrieval flow.
    
    Changes:
    - Sets state["sub_queries"] (list of self-contained questions)
    
    Args:
        model: The language model to use for decomposition
        query: The complex query string to decompose
        
    Returns:
        Updated state with sub_queries
    """
    
    # Call LLM to decompose query
    response = _llm.chat(
        query=query,
        chat_history=[],
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
    
    return sub_queries