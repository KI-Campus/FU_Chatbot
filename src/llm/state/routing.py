from src.llm.state.models import Scenario
from src.llm.objects.LLMs import LLM, Models
from src.llm.prompts.prompt_loader import load_prompt

# Load prompt
ROUTER_PROMPT = load_prompt("router_prompt")

def classify_scenario(query: str, model: Models) -> Scenario:
    """
    LLM-based classification of user query into scenario.
    
    Args:
        query: User's current query
        model: LLM model to use for classification
        
    Returns:
        Scenario classification
    """
    # Initialize LLM instance
    _llm = LLM()

    # Call LLM to classify scenario
    contextualized_question = _llm.chat(
        query=query, chat_history=[], model=model, system_prompt=ROUTER_PROMPT
    )
    
    if contextualized_question.content is None:
        raise ValueError(
            f"Contextualized question is None. Please check the LLM implementation. Response: {contextualized_question}"
        )

    return contextualized_question.content