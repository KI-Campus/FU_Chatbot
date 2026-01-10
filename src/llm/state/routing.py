from src.llm.state.models import Scenario
from src.llm.prompts.prompt_loader import load_prompt

# Load prompt
ROUTER_PROMPT = load_prompt("router_prompt")


def classify_scenario(query: str, chat_history_length: int = 0) -> Scenario:
    """
    Placeholder for LLM-based scenario classification.
    
    In actual implementation, this will call an LLM with ROUTER_PROMPT.
    For now, uses simple heuristics.
    
    Args:
        query: User's current query
        chat_history_length: Number of previous messages (for context)
        
    Returns:
        Scenario classification
    """
    query_lower = query.lower().strip()
    
    # Simple heuristics (to be replaced with LLM call)
    conversational_patterns = ["hallo", "hi", "danke", "okay", "gut", "verstanden", "tschüss", "bye"]
    socratic_patterns = ["hilf mir", "schritt für schritt", "erkläre", "zeig mir", "üben", "quiz"]
    multi_hop_patterns = ["vergleich", "unterschied zwischen", "wie hängen", "zusammenhang", "erkläre beide"]
    
    # no_vectordb: Very short conversational messages
    if len(query_lower) < 20 and any(pattern in query_lower for pattern in conversational_patterns):
        return "no_vectordb"
    
    # socratic: Explicit learning intent
    if any(pattern in query_lower for pattern in socratic_patterns):
        return "socratic"
    
    # multi_hop: Complex comparison/synthesis queries
    if any(pattern in query_lower for pattern in multi_hop_patterns) or len(query_lower.split()) > 15:
        return "multi_hop"
    
    # Default: simple_hop
    return "simple_hop"