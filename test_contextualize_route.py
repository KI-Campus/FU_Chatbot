"""Quick test for contextualize_and_route function."""

from src.llm.state.models import GraphState
from src.llm.tools.contextualize import contextualize_and_route
from src.llm.objects.LLMs import Models


# ============================================================================
# TEST CONFIGURATION - Modify values here
# ============================================================================
TEST_QUERY = "Was ist Deep Learning?"
CHAT_HISTORY = []  # Add chat history if needed, e.g., [ChatMessage(...), ...]
MODEL = Models.GPT4

# ============================================================================
# Test Execution
# ============================================================================

# Create initial state
state = GraphState(
    user_query=TEST_QUERY,
    chat_history=CHAT_HISTORY,
    runtime_config={
        "model": MODEL,
    },
    system_config={}
)

print("🧪 Testing contextualize_and_route...")
print("=" * 80)
print(f"📝 Original Query: {state['user_query']}")
print(f"💬 Chat History Length: {len(state['chat_history'])}")
print(f"🤖 Model: {MODEL.value}")
print("=" * 80)
print()

# Execute contextualize_and_route
result_state = contextualize_and_route(state)

# Display results
print("✅ RESULTS:")
print("=" * 80)
print(f"🔄 Contextualized Query: {result_state['contextualized_query']}")
print(f"🎯 Routing Mode: {result_state['mode']}")
print()
print("📊 Complete State Metadata:")
print("-" * 80)
print(f"  • user_query: {result_state['user_query']}")
print(f"  • contextualized_query: {result_state['contextualized_query']}")
print(f"  • mode: {result_state['mode']}")
print(f"  • chat_history: {len(result_state['chat_history'])} messages")
print(f"  • runtime_config: {result_state['runtime_config']}")
print(f"  • system_config: {result_state['system_config']}")
print()
print("=" * 80)
print("✅ Test complete!")
