"""Socratic subgraph implemented as a LangGraph planner/tool agent loop."""

from langgraph.graph import StateGraph, START

from src.llm.state.models import GraphState
from src.llm.tools.socratic_agent import (
    socratic_agent_planner,
    socratic_agent_tool_node,
    route_after_planner,
    route_after_tool,
)


def build_socratic_graph() -> StateGraph:
    """Build the socratic agent loop.

    The planner enforces contract and diagnosis via state guards before core tools.
    Core can choose question/hint/explain. Explain chains directly to feedback.
    """
    graph = StateGraph(GraphState)

    graph.add_node("socratic_agent_planner", socratic_agent_planner)
    graph.add_node("socratic_agent_tool_node", socratic_agent_tool_node)

    graph.add_edge(START, "socratic_agent_planner")
    graph.add_conditional_edges("socratic_agent_planner", route_after_planner)
    graph.add_conditional_edges("socratic_agent_tool_node", route_after_tool)

    return graph.compile()