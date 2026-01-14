import argparse

from langfuse import Langfuse
from llama_index.core.llms import ChatMessage, MessageRole
from src.llm.objects.LLMs import Models
from src.llm.assistant import KICampusAssistant

DEFAULT_COURSE_ID = 106
DEFAULT_MODULE_ID = 7152

RETRIEVE_TOP_N = 10
RERANK_TOP_N = 5

def parse_args():
    p = argparse.ArgumentParser(description="Interactive CLI chat with KICampusAssistant.")
    p.add_argument("--model", default="GPT4", help="Model enum name from Models, e.g. GPT4")
    p.add_argument("--course-id", type=int, default=DEFAULT_COURSE_ID, help="Optional Moodle course_id")
    p.add_argument("--module-id", type=int, default=DEFAULT_MODULE_ID, help="Optional module_id")
    p.add_argument("--rerank-top-n", type=int, default=RERANK_TOP_N, help="Assistant rerank_top_n")
    p.add_argument("--n-chunks", type=int, default=RETRIEVE_TOP_N, help="Number of chunks to retrieve")
    return p.parse_args()

def main():
    args = parse_args()

    # Model aus Enum holen
    try:
        model = getattr(Models, args.model)
    except AttributeError as e:
        raise SystemExit(
            f"Unknown model '{args.model}'. Available: {[m.name for m in Models]}"
        ) from e

    assistant = KICampusAssistant(rerank_top_n=args.rerank_top_n, retrieve_top_n=args.n_chunks)
    
    # Chat history wie im Frontend (in-memory, kein LangGraph State)
    chat_history = []
    
    print("\n=== KI-Campus Assistant (Interactive Mode) ===")
    print(f"Model: {model.value}")
    print(f"Course ID: {args.course_id}")
    print(f"Module ID: {args.module_id}")
    print("\nType 'quit' or 'exit' to end the session.\n")
    
    while True:
        # User input
        try:
            query = input("\n👤 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nSession beendet.")
            break
            
        if not query:
            continue
            
        if query.lower() in ["quit", "exit", "q"]:
            print("\nSession beendet.")
            break
        
        # Call assistant (OHNE conversation_id, nur mit chat_history)
        try:
            if args.course_id is not None or args.module_id is not None:
                response = assistant.chat_with_course(
                    query=query,
                    model=model,
                    course_id=args.course_id,
                    module_id=args.module_id,
                    chat_history=chat_history,
                    conversation_id=None,  # Keine Persistenz, nur in-memory
                )
            else:
                response = assistant.chat(
                    query=query,
                    model=model,
                    chat_history=chat_history,
                    conversation_id=None,  # Keine Persistenz, nur in-memory
                )
            
            # Output
            print(f"\n🤖 Assistant:\n{response.content}\n")
            
            # Update history (wie im Frontend)
            chat_history.append(ChatMessage(role=MessageRole.USER, content=query))
            chat_history.append(ChatMessage(role=MessageRole.ASSISTANT, content=response.content))
            
        except Exception as e:
            print(f"\n❌ Fehler: {e}\n")
            import traceback
            traceback.print_exc()
            continue

    # Langfuse flush
    try:
        Langfuse().flush()
    except Exception:
        pass

if __name__ == "__main__":
    main()
