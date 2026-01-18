from typing import List, Optional, Literal, Dict, Any, TypedDict

from llama_index.core.llms import ChatMessage
from llama_index.core.schema import TextNode
from src.api.models.serializable_chat_message import SerializableChatMessage
from src.api.models.serializable_text_node import SerializableTextNode

Scenario = Literal["no_vectordb", "simple_hop", "multi_hop", "socratic", "exit_complete"]
SocraticMode = Literal["contract", "diagnose", "core", "hinting", "reflection", "explain"]

class GraphState(TypedDict, total=False):
    # user input and context
    user_query: str
    chat_history: List[SerializableChatMessage]

    # classified scenario
    mode: Optional[Scenario]
    
    # runtime configuration (from API/Frontend)
    runtime_config: Dict[str, Any]  # model, course_id, module_id, thread_id
    
    # system configuration (hardcoded defaults, not exposed to frontend)
    system_config: Dict[str, Any]  # rerank_top_n and retrieval_k

    # shared intermediate artifacts
    contextualized_query: Optional[str]
    detected_language: Optional[str]

    # retrieval artifacts
    retrieved: List[SerializableTextNode]
    reranked: List[SerializableTextNode]

    # multi_hop specific artifacts
    sub_queries: List[str]  # Decomposed sub-questions for multi-hop
    multi_contexts: List[List[SerializableTextNode]]  # Retrieved contexts per sub-query (parallel)

    # socratic specific artifacts
    socratic_mode: Optional[SocraticMode]  # Internal routing: "contract" | "diagnose" | "core" | "hinting" | "reflection" | "explain"
    socratic_contract: Optional[Dict[str, bool]]  # {"allow_explain": bool, "allow_direct_answer": bool}
    #diagnostic
    learning_objective: Optional[str]  # Identified learning goal for the interaction
    student_model: Optional[Dict[str, Any]]  # for now only: {"mastery": "low"|"medium"|"high"}
    #core
    hint_level: int  # 0-3, tracks escalation of hints (0=no hints yet, 3=maximum help before explain)
    attempt_count: int  # Number of attempts student made at current question/concept
    stuckness_score: float  # 0.0-1.0, heuristic measure of student being stuck
    goal_achieved: bool  # Whether the learning objective has been reached

    # output
    answer: Optional[str]
    citations_markdown: Optional[str]


def get_chat_history_as_messages(state: GraphState) -> List[ChatMessage]:
    """Helper function to convert SerializableChatMessage to ChatMessage for LLM calls."""
    return [msg.to_chat_message() for msg in state.get("chat_history", [])]


def get_doc_as_textnodes(state: GraphState, node: str) -> List[TextNode]:
    """Helper function to convert SerializableTextNode to TextNode for component usage."""
    return [node.to_text_node() for node in state.get(node, [])]