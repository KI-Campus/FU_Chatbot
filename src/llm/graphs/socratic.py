"""
Socratic Subgraph - Guided learning assistant with didactic state machine.

For queries where the user signals desire for step-by-step guidance,
hints, or self-discovery rather than direct answers.

Implements a pedagogical state machine with 6 nodes:
- contract: Establish learning agreement
- diagnose: Assess baseline understanding
- core: Main Socratic questioning loop (with retrieval)
- hinting: Graduated hints (levels 1-3)
- reflection: Consolidate learning
- explain: Controlled explanation (fallback)

IMPORTANT: Multi-Turn Design
- Each node execution returns to user (gives one response)
- Next user request continues from stored socratic_mode
- No automatic node chaining (each turn = one node execution)
"""

from langgraph.graph import StateGraph, START, END

from src.llm.state.models import GraphState
from src.llm.tools.socratic_contract import socratic_contract
from src.llm.tools.socratic_diagnose import socratic_diagnose
from src.llm.tools.socratic_core import socratic_core
from src.llm.tools.socratic_explain import socratic_explain


def build_socratic_graph() -> StateGraph:
    """
    Builds the socratic subgraph with didactic state machine.
    
    Multi-Turn Architecture:
    - Each request executes EXACTLY ONE node, then returns to user
    - Router selects node based on socratic_mode from persisted state
    - Node sets socratic_mode for next turn
    - Graph always: START → [one node] → END
    
    Example Multi-Turn Flow:
    Request 1: socratic_mode=None     → Router → Contract → END (response to user)
    Request 2: socratic_mode="diagnose" → Router → Diagnose → END (response to user)
    Request 3: socratic_mode="core"    → Router → Core → END (response to user)
    Request 4: socratic_mode="core"    → Router → Core (question, hinting, reflection)→ END (response to user, loop)
    ...
    
    Node Transitions (via socratic_mode):
    - contract sets → "diagnose"
    - diagnose sets → "core"
    - core sets → "core" | "hinting" | "reflection" (based on progress)
    - hinting sets → "core" | "explain" (based on hint_level/contract)
    - explain sets → "reflection"
    - reflection sets → "complete" (terminal, no further requests expected)
    
    User Intent Detection (Phase 10):
    - Each node should check user_query for abort signals
    - "Gib mir die Antwort" → override socratic_mode to "explain"
    - "Lass uns was anderes machen" → exit socratic workflow
    """
    graph = StateGraph(GraphState)
    
    # Add socratic nodes (hinting and reflection are now part of core)
    graph.add_node("socratic_contract_node", socratic_contract)
    graph.add_node("socratic_diagnose_node", socratic_diagnose)
    graph.add_node("socratic_core_node", socratic_core)
    graph.add_node("socratic_explain_node", socratic_explain)
    
    # Router function: Selects ONE node based on socratic_mode
    def route_socratic_mode(state: GraphState) -> str:
        """
        Route to appropriate socratic node based on socratic_mode.
        
        Called at START of each request to determine which single node to execute.
        Default to "contract" if no socratic_mode set (first entry).
        """
        mode = state.get("socratic_mode")
        
        # Default to contract for first entry into socratic workflow
        if mode is None:
            return "socratic_contract_node"
        
        # Map socratic_mode to node names
        mode_to_node = {
            "contract": "socratic_contract_node",
            "diagnose": "socratic_diagnose_node",
            "core": "socratic_core_node",
            "explain": "socratic_explain_node",
        }
        
        return mode_to_node.get(mode, "socratic_contract_node")
    
    # START routes to exactly ONE node per request
    graph.add_conditional_edges(
        START,
        route_socratic_mode,
        {
            "socratic_contract_node": "socratic_contract_node",
            "socratic_diagnose_node": "socratic_diagnose_node",
            "socratic_core_node": "socratic_core_node",
            "socratic_explain_node": "socratic_explain_node",
        }
    )
    
    # ALL nodes lead directly to END (return to user after each node)
    graph.add_edge("socratic_contract_node", END)
    graph.add_edge("socratic_diagnose_node", END)
    graph.add_edge("socratic_core_node", END)
    graph.add_edge("socratic_explain_node", END)
    
    return graph.compile()