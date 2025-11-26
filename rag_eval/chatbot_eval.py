import asyncio
import json
from datetime import datetime
from typing import List
from openai import OpenAI

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import AnswerRelevancy, ContextRelevance, Faithfulness
from ragas import SingleTurnSample


# ---------------- CHATBOT CALL ----------------
def get_chatbot_answer(question: str) -> str:
    client = OpenAI()

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are the production chatbot."},
            {"role": "user", "content": question},
        ],
    )

    return resp.choices[0].message.content.strip()


# ---------------- MAIN ----------------
async def main():
    # Evaluator LLM used only for scoring
    evaluator_llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini"))

    # Embeddings needed for AnswerRelevancy
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    # Metrics
    metrics = [
        AnswerRelevancy(llm=evaluator_llm, embeddings=embeddings),
        ContextRelevance(llm=evaluator_llm),
        Faithfulness(llm=evaluator_llm),
    ]

    questions = [
        "What is artificial intelligence?",
        "What is supervised learning?",
    ]

    all_results = []
    metric_sums = {m.name: 0.0 for m in metrics}

    print("\n Starting evaluation...\n")

    for q in questions:
        print(f"\n============================\n Question: {q}")

        answer = get_chatbot_answer(q)
        contexts = []   # no documents

        print("\n Answer:")
        print(answer)

        sample = SingleTurnSample(
            user_input=q,
            response=answer,
            retrieved_contexts=contexts,
        )

        q_result = {"question": q, "answer": answer, "contexts": contexts, "metrics": {}}

        print("\n Scores:")
        for m in metrics:
            score = await m.single_turn_ascore(sample)
            score_val = float(score)
            q_result["metrics"][m.name] = score_val
            metric_sums[m.name] += score_val
            print(f"  - {m.name}: {score_val:.3f}")

        all_results.append(q_result)

    # Average metrics
    avg_scores = {name: metric_sums[name] / len(questions) for name in metric_sums}

    print("\n============================")
    print(" AVERAGE METRICS:")
    for name, avg in avg_scores.items():
        print(f"  - {name}: {avg:.3f}")

    # Save results
    out = {
        "results": all_results,
        "average_metrics": avg_scores,
    }

    outfile = f"noref_eval_all_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"\n Scores saved to {outfile}")


if __name__ == "__main__":
    asyncio.run(main())
