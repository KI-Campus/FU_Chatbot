import sys
import os
import asyncio
import json
from datetime import datetime
from functools import lru_cache  # <-- Added for caching

# Allow imports from project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# RAGAS
from ragas import SingleTurnSample
from ragas.metrics import AnswerRelevancy, ContextRelevance, Faithfulness
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas.llms import LangchainLLMWrapper

# Backend imports
from src.llm.LLMs import Models
from src.llm.assistant import KICampusAssistant


# ---------------- GET ANSWER + CONTEXT ----------------
def _get_answer_and_context(question: str):
    """Internal function — DO NOT call directly (cache wrapper below)."""
    assistant = KICampusAssistant()
    chat_history = []

    # contextualize
    rag_query = assistant.contextualizer.contextualize(
        query=question,
        chat_history=chat_history,
        model=Models.GPT4,
    )

    # retrieve
    retrieved_nodes = assistant.retriever.retrieve(rag_query)

    # extract contexts
    contexts = []
    for node in retrieved_nodes:
        try:
            if hasattr(node, "get_content"):
                contexts.append(node.get_content())
            else:
                contexts.append(node.text)
        except:
            pass

    # generate answer
    llm_response = assistant.chat(
        query=question,
        chat_history=chat_history,
        model=Models.GPT4,
    )

    return llm_response.content, contexts


# ---- SAFE SPEED OPTIMIZATION: CACHE RETRIEVAL + CONTEXTUALIZATION ----
@lru_cache(maxsize=None)
def get_answer_and_context(question: str):
    """Caches retrieval + contextualization (safe). DOES NOT cache the answer."""
    answer, contexts = _get_answer_and_context(question)
    return answer, tuple(contexts)  # must be hashable for cache
# ----------------------------------------------------------------------


# ---------------- MAIN ----------------
async def main():
    print("\nStarting evaluation...\n")

    # Evaluation LLM
    evaluator_llm = LangchainLLMWrapper(
        ChatOpenAI(model="gpt-4o", temperature=0)
    )

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    metrics = [
        AnswerRelevancy(llm=evaluator_llm, embeddings=embeddings),
        ContextRelevance(llm=evaluator_llm),
        Faithfulness(llm=evaluator_llm),
    ]

    # --------------------------------------------------
    # 50 Evaluation Questions by Category
    # --------------------------------------------------
    questions = [

        # 1. WISSEN ALLGEMEIN & KURSBEZOGEN (30)
        "Welche Lernstile werden dem Maschinellen Lernen zugrunde gelegt?",
        "Welche Potentiale oder Risiken entstehen durch KI für das Wohl von Patient:innen?",
        "Wie wird KI eingesetzt, um Krankheiten wie Krebs besser zu diagnostizieren?",
        "Welche Artikel des EU AI Act sind relevant für die Risikoklasse inakzeptables Risiko?",
        "Wie funktionieren Neuronale Netze?",
        "Welches der folgenden Ziele werden im EU AI Act verfolgt?",
        "Gibt es KI Luegendetektoren?",
        "Wie wird das Berufsbild des Mediziners durch Data Science verändert?",
        "What is AI thinking vs acting?",
        "Was sind BIAS?",
        "Was ist parametrization?",
        "Ich verstehe noch nicht ganz wie die KI-Winter entstehen?",
        "Wieviel Gigabyte Daten verwenden moderne LLMs?",
        "Wie erstelle ich eine Mermaid Mindmap mit KI?",
        "Was bedeutet: Ein System basierend aus GPU und Deep Learning?",
        "Was sind Gütekriterien bei der Datenerhebung?",
        "What is meant by 'canonical form' of a word?",
        "Welche LLM-Version nutzt Copilot aktuell?",
        "Gebe bitte einfache Beispiele für diskriminative KI.",
        "Wozu ist der KI-Lernassistent gedacht?",
        "Was bedeutet hier die Abkürzung HPI?",
        "Could you explain embeddings?",
        "Can you explain difference between LSTM and GRU?",
        "Can you explain how to create an LSTM with Python?",
        "Was ist tmin in python?",
        "Wenn man KI-Campus auf HessenHub OER-Spaeti mit Hilfe einer JSON-Datei ablegen möchte, welches Format sollte man wählen?",
        "Was sind Wireframes?",
        "McCulloch-Pitts 'Unit' Model of a Neuron?",
        "Wie erstelle ich mit KI eine Mindmap?",
        "In welchem Betriebssystem wird Python am besten genutzt?",

        # 2. TECHNISCHER SUPPORT (10)
        "Ich erhalte die Fehlermeldung 'The Vimeo video could not be loaded'. Was soll ich bitte tun?",
        "Wo finde ich den Prompt-Katalog?",
        "Wie kann ich mich registrieren?",
        "Kannst du auch Videos erstellen?",
        "Auf dieser Seite fehlt das Video: https://moodle.ki-campus.org/mod/videotime/view.php?id=22070&forceview=1",
        "Gibt es die Möglichkeit bei KI-Campus einen Lernpfad aus unterschiedlichen Formaten zusammenzustellen?",
        "Wie lade ich ein Foto hier hoch?",
        "Ich habe mein Passwort vergessen, aber es kommt keine Mail an. Woran kann das liegen?",
        "Hat der KI-Campus derzeit Server-Probleme?",
        "Ich kann 'Meine Kurse' nicht aufrufen. Ist die Seite down?",

        # 3. KURSMODALITÄTEN (7)
        "Lernziel-Check war negativ. Habe ich noch 2 Versuche?",
        "Wann erhält man einen Leistungsnachweis?",
        "Kann ich nur die Quiz machen, um das Zertifikat zu erhalten?",
        "Was kann ich mit den Badges der Plattform machen?",
        "Erscheint die Punktzahl auf dem Zertifikat?",
        "Reicht es, wenn ich nur alle Übungsaufgaben der Wochen beantworte?",
        "Was steht in der Teilnahmebestätigung und im Leistungsnachweis?",

        # 4. ANFRAGEN ZUR CHATBOTFUNKTION (3)
        "Ist das der Chatbot vom KI-Campus?",
        "Womit kannst du mir helfen?",
        "Zu welchen Themen kann ich dir Fragen stellen?",
    ]
    # --------------------------------------------------

    N_REPEATS = 5

    all_results = []
    global_metric_sums = {m.name: 0.0 for m in metrics}
    global_metric_count = 0

    for q in questions:
        print(f"\n============================\nQuestion: {q}")
        per_question_metric_sums = {m.name: 0.0 for m in metrics}

        repeats = []

        # --- Cached retrieval (retrieval runs ONCE only) ---
        first_answer, contexts = get_answer_and_context(q)

        print("\nRetrieved Contexts (first 2):")
        for c in list(contexts)[:2]:
            print("-", c[:250], "...")

        # Now only regenerate the ANSWER in repeats
        for run_idx in range(N_REPEATS):
            print(f"\n--- Run {run_idx + 1}/{N_REPEATS} ---")

            # --- Regenerate answer (not cached) ---
            answer, _ = _get_answer_and_context(q)

            # Show answer before scoring
            print("\nAnswer for this run:\n")
            print(answer)

            sample = SingleTurnSample(
                user_input=q,
                response=answer,
                retrieved_contexts=list(contexts),
            )

            run_result = {
                "run": run_idx + 1,
                "answer": answer,
                "contexts": list(contexts),
                "metrics": {}
            }

            for m in metrics:
                score = float(await m.single_turn_ascore(sample))
                run_result["metrics"][m.name] = score
                per_question_metric_sums[m.name] += score
                global_metric_sums[m.name] += score
                print(f"  - {m.name}: {score:.3f}")

            repeats.append(run_result)
            global_metric_count += 1

        per_question_avg = {
            name: per_question_metric_sums[name] / N_REPEATS
            for name in per_question_metric_sums
        }

        all_results.append({
            "question": q,
            "runs": repeats,
            "average_metrics": per_question_avg
        })

        print("\nAverage for question:")
        for name, avg in per_question_avg.items():
            print(f"  - {name}: {avg:.3f}")

    global_avg = {
        name: global_metric_sums[name] / global_metric_count
        for name in global_metric_sums
    }

    print("\n============================")
    print("GLOBAL AVERAGE METRICS (across all questions & repeats):")
    for name, avg in global_avg.items():
        print(f"  - {name}: {avg:.3f}")

    output = {
        "results": all_results,
        "global_average_metrics": global_avg,
        "repetitions": N_REPEATS
    }

    outfile = f"chatbot_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nSaved results to {outfile}")


if __name__ == "__main__":
    asyncio.run(main())
