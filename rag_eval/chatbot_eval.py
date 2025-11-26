import sys
import os
import asyncio
import json
from datetime import datetime

# Allow imports from project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# RAGAS
from ragas import SingleTurnSample
from ragas.metrics import AnswerRelevancy, ContextRelevance, Faithfulness
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas.llms import LangchainLLMWrapper

# Backend imports
from src.api.rest import chat, ChatRequest
from src.api.models.serializable_chat_message import SerializableChatMessage
from src.llm.LLMs import Models
from src.llm.assistant import KICampusAssistant
from llama_index.core.llms import MessageRole


# ---------------- GET ANSWER + CONTEXT ----------------
def get_answer_and_context(question: str):
    """
    Returns:
    - answer from chatbot
    - contexts retrieved from Qdrant (list[str])
    """

    # Build ChatRequest just like FastAPI
    chat_request = ChatRequest(
        messages=[
            SerializableChatMessage(
                content=question,
                role=MessageRole.USER
            )
        ],
        course_id=None,
        module_id=None,
        model=Models.GPT4
    )

    assistant = KICampusAssistant()

    # 1) Retrieve context (RAG retrieval BEFORE generation)
    retrieved_nodes = assistant.retriever.retrieve(question)

    contexts = []
    for node in retrieved_nodes:
        try:
            contexts.append(node.text)
        except:
            pass  # skip broken nodes

    # 2) Generate answer using full RAG pipeline
    response = chat(chat_request)

    return response.message, contexts


# ---------------- MAIN ----------------
async def main():
    print("\nStarting evaluation...\n")

    # Evaluator LLM for RAGAS (async-safe)
    evaluator_llm = LangchainLLMWrapper(
        ChatOpenAI(model="gpt-4o-mini", temperature=0)
    )

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    metrics = [
        AnswerRelevancy(llm=evaluator_llm, embeddings=embeddings),
        ContextRelevance(llm=evaluator_llm),
        Faithfulness(llm=evaluator_llm),
    ]

    questions = [
        "What is artificial intelligence?",
        "What is K-means clustering?",
        "Wo finde ich meine Kurse?"
    ]

    all_results = []
    metric_sums = {m.name: 0.0 for m in metrics}

    for q in questions:
        print(f"\n============================\nQuestion: {q}")

        answer, contexts = get_answer_and_context(q)

        print("\nAnswer:")
        print(answer)

        print("\nRetrieved Contexts (first 2):")
        for c in contexts[:2]:
            print("-", c[:200], "...")

        # Build RAGAS sample
        sample = SingleTurnSample(
            user_input=q,
            response=answer,
            retrieved_contexts=contexts,
        )

        q_result = {
            "question": q,
            "answer": answer,
            "contexts": contexts,
            "metrics": {},
        }

        print("\nScores:")
        for m in metrics:
            score = await m.single_turn_ascore(sample)
            score = float(score)
            q_result["metrics"][m.name] = score
            metric_sums[m.name] += score
            print(f"  - {m.name}: {score:.3f}")

        all_results.append(q_result)

    # Average metrics
    avg_scores = {k: metric_sums[k] / len(questions) for k in metric_sums}

    print("\n============================")
    print("AVERAGE METRICS:")
    for name, avg in avg_scores.items():
        print(f"  - {name}: {avg:.3f}")

    # Save results
    output = {
        "results": all_results,
        "average_metrics": avg_scores,
    }

    outfile = f"chatbot_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nSaved results to {outfile}")


if __name__ == "__main__":
    asyncio.run(main())
