from typing import List, Optional, Literal, Dict, Any, TypedDict

from llama_index.core.schema import TextNode
from src.api.models.serializable_chat_message import SerializableChatMessage
from src.api.models.serializable_text_node import SerializableTextNode

Scenario = Literal["no_vectordb", "simple_hop", "multi_hop", "socratic", "exit_complete"]
SocraticAgentPhase = Literal["contract", "diagnosis", "core", "feedback", "complete"]
SocraticCoreTool = Literal["question", "hint", "explain"]


class SocraticAgentState(TypedDict, total=False):
    active: bool
    phase: SocraticAgentPhase
    contract_artifact: Optional[str]
    diagnosis_artifact: Optional[str]
    learning_objective: Optional[str]
    attempt_count: int
    number_given_hints: int
    feedback_required: bool
    feedback_done: bool
    last_core_tool: Optional[SocraticCoreTool]
    last_executed_tool: Optional[str]
    planned_tool: Optional[str]
    pending_feedback_prefix: Optional[str]


def build_inactive_socratic_agent_state() -> SocraticAgentState:
    return {
        "active": False,
        "phase": "complete",
        "contract_artifact": None,
        "diagnosis_artifact": None,
        "learning_objective": None,
        "attempt_count": 0,
        "number_given_hints": 0,
        "feedback_required": False,
        "feedback_done": False,
        "last_core_tool": None,
        "last_executed_tool": None,
        "planned_tool": None,
        "pending_feedback_prefix": None,
    }


def build_active_socratic_agent_state() -> SocraticAgentState:
    state = build_inactive_socratic_agent_state()
    state["active"] = True
    state["phase"] = "contract"
    return state

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

    # socratic agent state
    socratic_agent: SocraticAgentState

    # output
    answer: Optional[str]
    citations_markdown: Optional[str]


def get_doc_as_textnodes(state: GraphState, node: str) -> List[TextNode]:
    """Helper function to convert SerializableTextNode to TextNode for component usage."""
    return [node.to_text_node() for node in state.get(node, [])]