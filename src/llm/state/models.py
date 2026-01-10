from typing import List, Optional, Literal, Dict, Any, TypedDict

from llama_index.core.llms import ChatMessage
from llama_index.core.schema import TextNode

Scenario = Literal["no_vectordb", "simple_hop", "multi_hop", "socratic"]

class GraphState(TypedDict, total=False):
    mode: Optional[Scenario]
    user_query: str
    chat_history: List[ChatMessage]
    
    # runtime configuration (from API/Frontend)
    runtime_config: Dict[str, Any]  # model, course_id, module_id, conversation_id
    
    # system configuration (hardcoded defaults, not exposed to frontend)
    system_config: Dict[str, Any]  # rerank_top_n, retrieval_k, timeouts, etc.

    # shared intermediate artifacts
    contextualized_query: Optional[str]
    detected_language: Optional[str]

    # retrieval artifacts
    retrieved: List[TextNode]
    reranked: List[TextNode]

    # multihop specific artifacts
    #VOERST DIESE ABER ICH MÖCHTE DIE UMSETZUNG NOCHMAL ÜBERDENKEN
    """
    sub_queries: List[str] = []
    sub_query_answers: List[str] = []
    """

    # socratic specific artifacts
    #VOERST DIESE ABER ICH MÖCHTE DIE UMSETZUNG NOCHMAL ÜBERDENKEN
    """
    learning_goal: Optional[str] = None
    student_model: Dict[str, Any] = {}
    socratic_steps: Optional[str] = None # 'ask', 'hint', 'explain', 'quiz' ...
    """

    # output
    answer: Optional[str] = None
    citations_markdown: Optional[str] = None