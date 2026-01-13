from langfuse.decorators import observe, langfuse_context
from llama_index.core.llms import ChatMessage, MessageRole
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.llm.objects.LLMs import Models
from src.llm.state.models import GraphState
from src.llm.tools.contextualize import contextualize_and_route
from src.llm.graphs.no_vector_db import build_no_vectordb_graph
from src.llm.graphs.simple_hop import build_simple_hop_graph
from src.llm.graphs.multi_hop import build_multi_hop_graph
from src.llm.graphs.socratic import build_socratic_graph


class KICampusAssistant:
    """
    Main RAG assistant orchestrator using LangGraph.
    
    Routes queries to appropriate subgraphs based on scenario classification.
    """
    
    def __init__(self, rerank_top_n: int = 5):
        """
        Initialize the assistant with system configuration.
        
        Args:
            rerank_top_n: Number of top chunks to keep after reranking
        """
        # System configuration (hardcoded, not exposed to frontend)
        self.system_config = {
            "rerank_top_n": rerank_top_n,
        }
        
        # Initialize checkpoint/persistence backend
        # MemorySaver for development - replace with PostgresSQL for production
        self.checkpointer = MemorySaver()
        
        # Compile main router graph once (singleton pattern for performance)
        self.graph = self._build_main_graph()
    
    def _build_main_graph(self) -> StateGraph:
        """
        Builds the main router graph that routes to scenario-specific subgraphs.
        
        Flow:
        START → contextualize_and_route → [conditional routing based on mode] → END
        
        Scenarios:
        - no_vectordb: Conversational queries
        - simple_hop: Standard RAG
        - multi_hop: Complex multi-retrieval (placeholder)
        - socratic: Guided learning (placeholder)
        """
        # Compile subgraphs
        no_vectordb_graph = build_no_vectordb_graph()
        simple_hop_graph = build_simple_hop_graph()
        multi_hop_graph = build_multi_hop_graph()
        socratic_graph = build_socratic_graph()
        
        # Main router graph
        graph = StateGraph(GraphState)
        
        # Add contextualize/routing node
        graph.add_node("contextualize_and_route", contextualize_and_route)
        
        # Add subgraph nodes
        graph.add_node("no_vectordb", no_vectordb_graph)
        graph.add_node("simple_hop", simple_hop_graph)
        graph.add_node("multi_hop", multi_hop_graph)
        graph.add_node("socratic", socratic_graph)
        
        # Start with contextualization and routing
        graph.add_edge(START, "contextualize_and_route")
        
        # Conditional routing based on mode
        def route_by_mode(state: GraphState) -> str:
            """Route to appropriate subgraph based on classified scenario."""
            return state["mode"]  # Returns "no_vectordb", "simple_hop", "multi_hop", or "socratic"
        
        graph.add_conditional_edges(
            "contextualize_and_route",
            route_by_mode,
            {
                "no_vectordb": "no_vectordb",
                "simple_hop": "simple_hop",
                "multi_hop": "multi_hop",
                "socratic": "socratic",
            }
        )
        
        # All subgraphs end at END
        graph.add_edge("no_vectordb", END)
        graph.add_edge("simple_hop", END)
        graph.add_edge("multi_hop", END)
        graph.add_edge("socratic", END)
        
        return graph.compile(checkpointer=self.checkpointer)

    @observe()
    def limit_chat_history(self, chat_history: list[ChatMessage], limit: int) -> list[ChatMessage]:
        """Limit chat history to last N messages to save context window."""
        if len(chat_history) > limit:
            chat_history = chat_history[-limit:]
        return chat_history

    @observe()
    def chat(self, query: str, model: Models, chat_history: list[ChatMessage] | None = None, conversation_id: str | None = None) -> ChatMessage:
        langfuse_context.update_current_observation(
            metadata={
                "conversation_id": conversation_id
            }
        )
        """
        Chat with general bot about drupal and functions of ki-campus.
        For frontend integrated in Drupal.
        
        Args:
            query: User's question
            model: LLM model to use
            chat_history: Previous conversation messages
            conversation_id: Optional thread ID for persistent conversations
            
        Returns:
            ChatMessage with answer (including citations)
        """
        if chat_history is None:
            chat_history = []

        # Limit context window to save resources
        limited_chat_history = self.limit_chat_history(chat_history, 10)

        # Create initial state
        initial_state: GraphState = {
            "user_query": query,
            "chat_history": limited_chat_history,
            "runtime_config": {
                "model": model,
                "conversation_id": conversation_id,
                # No course_id/module_id for general chat
            },
            "system_config": self.system_config
        }

        # Thread config for LangGraph persistence
        config = {
            "configurable": {
                "thread_id": conversation_id or "default"
            }
        }

        # Execute graph with persistence
        result = self.graph.invoke(initial_state, config=config)

        # Return as ChatMessage for backward compatibility
        return ChatMessage(
            role=MessageRole.ASSISTANT,
            content=result.get("citations_markdown") or result.get("answer") or ""
        )

    @observe()
    def chat_with_course(
        self,
        query: str,
        model: Models,
        course_id: int | None = None,
        chat_history: list[ChatMessage] | None = None,
        module_id: int | None = None,
        conversation_id: str | None = None,
    ) -> ChatMessage:
        """
        Chat with the contents of a specific course and optionally submodule.
        For frontend hosted on Moodle.
        
        Args:
            query: User's question
            model: LLM model to use
            course_id: Moodle course ID to filter by
            chat_history: Previous conversation messages
            module_id: Optional module/topic ID within course
            conversation_id: Optional thread ID for persistent conversations
            
        Returns:
            ChatMessage with answer (including citations)
        """
        langfuse_context.update_current_observation(
            metadata={
                "conversation_id": conversation_id
            }
        )

        if chat_history is None:
            chat_history = []

        limited_chat_history = self.limit_chat_history(chat_history, 10)

        # Create initial state with course filters
        initial_state: GraphState = {
            "user_query": query,
            "chat_history": limited_chat_history,
            "runtime_config": {
                "model": model,
                "course_id": course_id,
                "module_id": module_id,
                "conversation_id": conversation_id,
            },
            "system_config": self.system_config
        }

        # Thread config for LangGraph persistence
        config = {
            "configurable": {
                "thread_id": conversation_id or "default"
            }
        }

        # Execute graph with persistence
        result = self.graph.invoke(initial_state, config=config)

        # Return as ChatMessage for backward compatibility
        return ChatMessage(
            role=MessageRole.ASSISTANT,
            content=result.get("citations_markdown") or result.get("answer") or ""
        )


if __name__ == "__main__":
    assistant = KICampusAssistant()
    assistant.chat(query="Eklär über den Kurs Deep Learning mit Tensorflow, Keras und Tensorflow.js", model=Models.GPT4)
