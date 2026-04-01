"""LangGraph-based Socratic agent planner and tool executor."""

from __future__ import annotations

from typing import Literal

from langfuse.decorators import observe
from langgraph.graph import END

from src.llm.state.models import (
    GraphState,
    SocraticAgentState,
    build_active_socratic_agent_state,
    build_inactive_socratic_agent_state,
)
from src.llm.state.socratic_routing import evaluate_user_response
from src.llm.tools.retrieve import retrieve_chunks
from src.llm.tools.rerank import rerank_chunks
from src.llm.tools.socratic_contract import socratic_contract
from src.llm.tools.socratic_diagnose import socratic_diagnose
from src.llm.tools.socratic_explain import socratic_explain
from src.llm.tools.socratic_hinting import generate_hint_text
from src.llm.tools.socratic_question import generate_socratic_question
from src.llm.tools.socratic_reflection import generate_reflection_text

MAX_HINTS_BEFORE_EXPLAIN = 2
SOCRATIC_FINAL_FAREWELL = "Der Lernmodus ist jetzt beendet. Wenn du weitere Fragen hast, helfe ich dir gerne im normalen Chat weiter."


def _active_agent_state(state: GraphState) -> SocraticAgentState:
    return {
        **build_active_socratic_agent_state(),
        **(state.get("socratic_agent") or {}),
    }


def _get_reranked_chunks_for_core(state: GraphState) -> list:
    working_state = dict(state)

    if not working_state.get("contextualized_query"):
        working_state["contextualized_query"] = state["user_query"]

    if "system_config" not in working_state:
        working_state["system_config"] = {
            "retrieve_top_n": 10,
            "rerank_top_n": 5,
        }

    retrieved_update = retrieve_chunks(working_state)
    working_state.update(retrieved_update)

    reranked_update = rerank_chunks(working_state)
    return reranked_update.get("reranked", [])


@observe(name="socratic_agent_planner")
def socratic_agent_planner(state: GraphState) -> dict:
    """Plan the next Socratic tool according to hard phase guards."""
    agent = _active_agent_state(state)

    if not agent.get("active", False):
        return {"socratic_agent": {**agent, "planned_tool": None}}

    if not agent.get("contract_artifact"):
        planned_tool = "contract"
        phase = "contract"
    elif not agent.get("diagnosis_artifact"):
        planned_tool = "diagnosis"
        phase = "diagnosis"
    elif agent.get("feedback_required", False) and not agent.get("feedback_done", False):
        planned_tool = "feedback"
        phase = "feedback"
    else:
        attempt_count = int(agent.get("attempt_count", 0)) + 1
        hint_count = int(agent.get("number_given_hints", 0))

        if hint_count >= MAX_HINTS_BEFORE_EXPLAIN:
            planned_tool = "explain"
        else:
            mode = evaluate_user_response(
                user_query=state["user_query"],
                chat_history=state["chat_history"],
                learning_objective=agent.get("learning_objective") or state["user_query"],
                attempt_count=attempt_count,
                model=state["runtime_config"]["model"],
            )

            if mode == "EXPLAIN":
                planned_tool = "explain"
            elif mode == "HINT":
                planned_tool = "hint"
            elif mode == "REFLECT":
                planned_tool = "feedback"
            else:
                planned_tool = "question"

        phase = "feedback" if planned_tool == "feedback" else "core"

    return {
        "socratic_agent": {
            **agent,
            "phase": phase,
            "planned_tool": planned_tool,
        }
    }


@observe(name="socratic_agent_tool_node")
def socratic_agent_tool_node(state: GraphState) -> dict:
    """Execute the tool selected by the planner."""
    agent = _active_agent_state(state)
    planned_tool = agent.get("planned_tool")

    if not planned_tool:
        return {}

    if planned_tool == "contract":
        return socratic_contract(state)

    if planned_tool == "diagnosis":
        return socratic_diagnose(state)

    if planned_tool == "question":
        return _run_question_tool(state, agent)

    if planned_tool == "hint":
        return _run_hint_tool(state, agent)

    if planned_tool == "explain":
        return _run_explain_tool(state, agent)

    if planned_tool == "feedback":
        return _run_feedback_tool(agent)

    raise ValueError(f"Unknown socratic tool: {planned_tool}")


def route_after_planner(state: GraphState) -> Literal["socratic_agent_tool_node", "__end__"]:
    """Route to tool node if planner selected a tool."""
    agent = state.get("socratic_agent") or {}
    if agent.get("planned_tool"):
        return "socratic_agent_tool_node"
    return END


def route_after_tool(state: GraphState) -> Literal["socratic_agent_planner", "__end__"]:
    """Only loop when explain completed and feedback still must be emitted."""
    agent = state.get("socratic_agent") or {}
    if (
        agent.get("last_executed_tool") == "explain"
        and agent.get("feedback_required", False)
        and not agent.get("feedback_done", False)
    ):
        return "socratic_agent_planner"
    return END


def _run_question_tool(state: GraphState, agent: SocraticAgentState) -> dict:
    reranked = _get_reranked_chunks_for_core(state)
    new_attempt_count = int(agent.get("attempt_count", 0)) + 1

    response = generate_socratic_question(
        learning_objective=agent.get("learning_objective") or state["user_query"],
        user_query=state["user_query"],
        reranked=reranked,
        chat_history=state["chat_history"],
        new_attempt_count=new_attempt_count,
        model=state["runtime_config"]["model"],
    )

    return {
        "socratic_agent": {
            **agent,
            "phase": "core",
            "attempt_count": new_attempt_count,
            "last_core_tool": "question",
            "last_executed_tool": "question",
            "planned_tool": None,
        },
        "answer": response,
        "citations_markdown": None,
    }


def _run_hint_tool(state: GraphState, agent: SocraticAgentState) -> dict:
    reranked = _get_reranked_chunks_for_core(state)
    new_attempt_count = int(agent.get("attempt_count", 0)) + 1
    new_hint_count = int(agent.get("number_given_hints", 0)) + 1

    response = generate_hint_text(
        learning_objective=agent.get("learning_objective") or state["user_query"],
        user_query=state["user_query"],
        reranked_chunks=reranked,
        chat_history=state["chat_history"],
        number_given_hints=new_hint_count,
        model=state["runtime_config"]["model"],
    )

    return {
        "socratic_agent": {
            **agent,
            "phase": "core",
            "attempt_count": new_attempt_count,
            "number_given_hints": new_hint_count,
            "last_core_tool": "hint",
            "last_executed_tool": "hint",
            "planned_tool": None,
        },
        "answer": response,
        "citations_markdown": None,
    }


def _run_explain_tool(state: GraphState, agent: SocraticAgentState) -> dict:
    reranked = _get_reranked_chunks_for_core(state)
    new_attempt_count = int(agent.get("attempt_count", 0)) + 1

    response = socratic_explain(
        learning_objective=agent.get("learning_objective") or state["user_query"],
        user_query=state["user_query"],
        reranked_chunks=reranked,
        chat_history=state["chat_history"],
        attempt_count=new_attempt_count,
        number_given_hints=int(agent.get("number_given_hints", 0)),
        model=state["runtime_config"]["model"],
    )

    return {
        "socratic_agent": {
            **agent,
            "phase": "feedback",
            "attempt_count": new_attempt_count,
            "feedback_required": True,
            "feedback_done": False,
            "last_core_tool": "explain",
            "last_executed_tool": "explain",
            "planned_tool": None,
            "pending_feedback_prefix": response,
        },
        "answer": response,
        "citations_markdown": None,
    }


def _run_feedback_tool(agent: SocraticAgentState) -> dict:
    feedback_text = generate_reflection_text(
        learning_objective=agent.get("learning_objective")
    )

    pending_prefix = agent.get("pending_feedback_prefix")
    if pending_prefix:
        final_message = f"{pending_prefix}\n\n{feedback_text}\n\n{SOCRATIC_FINAL_FAREWELL}"
    else:
        final_message = f"{feedback_text}\n\n{SOCRATIC_FINAL_FAREWELL}"

    finished_agent = {
        **build_inactive_socratic_agent_state(),
        "last_executed_tool": "feedback",
        "feedback_done": True,
    }

    return {
        "socratic_agent": finished_agent,
        "answer": final_message,
        "citations_markdown": None,
    }
