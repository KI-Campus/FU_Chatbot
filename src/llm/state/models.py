from typing import List, Optional, Literal, Dict, Any, TypedDict

from llama_index.core.llms import ChatMessage
from llama_index.core.schema import TextNode

Scenario = Literal["no_vectordb", "simple_hop", "multi_hop", "socratic"]
SocraticMode = Literal["contract", "diagnose", "core", "hinting", "reflection", "explain"]

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

    # multi_hop specific artifacts
    sub_queries: List[str]  # Decomposed sub-questions for multi-hop
    multi_contexts: List[List[TextNode]]  # Retrieved contexts per sub-query (parallel)

    # socratic specific artifacts
    socratic_mode: Optional[SocraticMode]  # Internal routing: "contract" | "diagnose" | "core" | "hinting" | "reflection" | "explain"
    socratic_contract: Optional[Dict[str, bool]]  # {"allow_explain": bool, "allow_direct_answer": bool}
    #diagnostic
    learning_objective: Optional[str]  # Identified learning goal for the interaction
    student_model: Optional[Dict[str, Any]]  # {"mastery": "low"|"med"|"high", "misconceptions": [], "affect": ...}
    #core
    hint_level: int  # 0-3, tracks escalation of hints (0=no hints yet, 3=maximum help before explain)
    attempt_count: int  # Number of attempts student made at current question/concept
    stuckness_score: float  # 0.0-1.0, heuristic measure of student being stuck (>0.7 triggers hinting)
    goal_achieved: bool  # Whether the learning objective has been reached

    # output
    answer: Optional[str]
    citations_markdown: Optional[str]