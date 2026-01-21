import sys
import os
import asyncio
import json
import logging
from datetime import datetime
from functools import lru_cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Allow imports from project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# RAGAS
from ragas import SingleTurnSample
from ragas.metrics import AnswerRelevancy, ContextRelevance, Faithfulness
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas.llms import LangchainLLMWrapper

# Backend imports
from src.llm.objects.LLMs import Models
from src.llm.assistant import KICampusAssistant
from src.llm.objects.contextualizer import Contextualizer
from src.llm.tools.retrieve import get_retriever


# ---------------- CONTEXT RETRIEVAL (CACHED) ----------------
def _retrieve_context(question: str):
    contextualizer = Contextualizer()
    retriever = get_retriever(use_hybrid=True, n_chunks=10)
    chat_history = []

    rag_query = contextualizer.contextualize(
        query=question,
        chat_history=chat_history,
        model=Models.GPT4,
    )

    retrieved_nodes = retriever.retrieve(rag_query)

    contexts = []
    for node in retrieved_nodes:
        try:
            if hasattr(node, "get_content"):
                contexts.append(node.get_content())
            else:
                contexts.append(node.text)
        except Exception as e:
            logger.error(f"Failed to extract content from node: {e}")

    return tuple(contexts)


@lru_cache(maxsize=None)
def get_context(question: str):
    """Caches retrieval + contextualization only."""
    return _retrieve_context(question)


# ---------------- ANSWER GENERATION (NOT CACHED) ----------------
def generate_answer(question: str):
    assistant = KICampusAssistant()

    response, _ = assistant.chat(
        query=question,
        model=Models.GPT4,
    )

    return response.content


# ---------------- MAIN ----------------
async def main():
    print("\nStarting evaluation...\n")

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
    # Evaluation Questions
    # --------------------------------------------------
    questions = [

        # 1. WISSEN ALLGEMEIN & KURSBEZOGEN (30)
        "Welche Lernstile werden dem Maschinellen Lernen zugrunde gelegt?",
        "Welche Potentiale oder Risiken entstehen durch KI für das Wohl von Patient:innen?",
        "Wie wird KI eingesetzt, um Krankheiten wie Krebs besser zu diagnostizieren?",
        "Welche Artikel des EU AI Act sind relevant für die Risikoklasse inakzeptables Risiko?",
        "Wie funktionieren Neuronale Netze?",
        "Welches der folgenden Ziele werden im EU AI Act verfolgt?",
        "Gibt es KI-Lügendetektoren?",
        "Wie wird das Berufsbild des Mediziners durch Data Science verändert?",
        "What is AI thinking vs acting?",
        "Was sind BIAS?",
        "Was ist Parametrisierung?",
        "Ich verstehe noch nicht ganz, wie die KI-Winter entstehen?",
        "Welche Faktoren beeinflussen die Qualität von Antworten eines Large Language Models?",
        "Wie erstelle ich eine Mermaid Mindmap mit KI?",
        "Was bedeutet: Ein System basierend auf GPU und Deep Learning?",
        "Was sind Gütekriterien bei der Datenerhebung?",
        "Was versteht man unter Datenvorverarbeitung im Kontext von Machine Learning?",
        "Welche Rolle spielen Trainingsdaten bei der Leistungsfähigkeit von KI-Modellen?",
        "Gebe bitte einfache Beispiele für diskriminative KI.",
        "Wozu ist der KI-Lernassistent gedacht?",
        "Was bedeutet die Abkürzung HPI?",
        "Could you explain embeddings?",
        "Can you explain the difference between LSTM and GRU?",
        "Can you explain how to create an LSTM with Python?",
        "Was ist tmin in Python?",
        "Wenn man KI-Campus auf HessenHub OER-Spaeti mit Hilfe einer JSON-Datei ablegen möchte, welches Format sollte man wählen?",
        "What are PROs and CONs of XAI Methods?",
        "Welche Grundkonzepte des Maschinellen Lernens werden in den KI-Campus-Kursen vermittelt?",
        "Was ist der Unterschied zwischen überwachten, unüberwachten und bestärkenden Lernverfahren?",
        "Welche Programmiersprachen werden im Bereich Data Science häufig eingesetzt?",

        # 2. TECHNISCHER SUPPORT (10)
        "Ich erhalte die Fehlermeldung 'The Vimeo video could not be loaded'. Was soll ich tun?",
        "Wo finde ich den Prompt-Katalog?",
        "Wie kann ich mich registrieren?",
        "Kannst du auch Videos erstellen?",
        "Auf dieser Seite wird kein Video angezeigt: https://moodle.ki-campus.org/mod/videotime/view.php?id=22070&forceview=1. Woran kann das liegen?",
        "Gibt es die Möglichkeit, bei KI-Campus einen Lernpfad aus unterschiedlichen Formaten zusammenzustellen?",
        "Wie lade ich ein Foto hoch?",
        "Ich habe mein Passwort vergessen, aber es kommt keine Mail an. Woran kann das liegen?",
        "Wie informiert der KI-Campus Nutzer:innen über technische Störungen oder Wartungsarbeiten?",
        "Ich kann 'Meine Kurse' nicht aufrufen. Ist die Plattform derzeit nicht erreichbar?",

        # 3. KURSMODALITÄTEN (10)
        "Lernziel-Check war negativ. Habe ich noch 2 Versuche?",
        "Wann erhält man einen Leistungsnachweis?",
        "Kann ich nur die Quiz machen, um das Zertifikat zu erhalten?",
        "Was kann ich mit den Badges der Plattform machen?",
        "Erscheint die Punktzahl auf dem Zertifikat?",
        "Reicht es, wenn ich nur alle Übungsaufgaben der Wochen beantworte?",
        "Was steht in der Teilnahmebestätigung und im Leistungsnachweis?",
        "Für welche Kurse ist ein Micro-Degree erhältlich?",
        "Are you accessible for free?",
        "Wie viele Module umfasst der Kurs?",

        # 4. ANFRAGEN ZUR CHATBOTFUNKTION (10)
        "Zu welchen Themen kann ich dir Fragen stellen?",
        "Ich möchte selbst einen Chatbot erstellen. Kannst du mir dabei helfen?",
        "What extra value do you bring for me as a student?",
        "Do you have information only about AI topics?",
        "Gibt es auf dieser Seite Quiz, um den Wissensstand zu testen? Wo genau finde ich diese?",
        "Kannst du mir bei der Orientierung auf der Plattform helfen?",
        "Wie gehst du vor, wenn du eine Frage nicht sicher beantworten kannst?",
        "Can you explain how you use provided documents to answer questions?",
        "Welche Einschränkungen hast du als Chatbot?",
        "Willst du mir verraten, wie du als Chatbot konstruiert bist?"
    ]

    # --------------------------------------------------

    N_REPEATS = 5

    all_results = []
    global_metric_sums = {m.name: 0.0 for m in metrics}
    global_metric_count = 0

    for q in questions:
        print(f"\n============================\nQuestion: {q}")
        per_question_metric_sums = {m.name: 0.0 for m in metrics}

        contexts = get_context(q)

        print("\nRetrieved Contexts (first 2):")
        for c in list(contexts)[:2]:
            print("-", c[:250], "...")

        runs = []

        for run_idx in range(N_REPEATS):
            print(f"\n--- Run {run_idx + 1}/{N_REPEATS} ---")

            answer = generate_answer(q)

            print("\nAnswer:\n")
            print(answer)

            sample = SingleTurnSample(
                user_input=q,
                response=answer,
                retrieved_contexts=list(contexts),
            )

            run_metrics = {}

            for m in metrics:
                score = float(await m.single_turn_ascore(sample))
                run_metrics[m.name] = score
                per_question_metric_sums[m.name] += score
                global_metric_sums[m.name] += score
                print(f"  - {m.name}: {score:.3f}")

            runs.append({
                "run": run_idx + 1,
                "answer": answer,
                "metrics": run_metrics
            })

            global_metric_count += 1

        avg_metrics = {
            k: v / N_REPEATS for k, v in per_question_metric_sums.items()
        }

        all_results.append({
            "question": q,
            "contexts": list(contexts),
            "runs": runs,
            "average_metrics": avg_metrics
        })

        print("\nAverage for question:")
        for name, avg in avg_metrics.items():
            print(f"  - {name}: {avg:.3f}")

    global_avg = {
        name: global_metric_sums[name] / global_metric_count
        for name in global_metric_sums
    }

    print("\n============================")
    print("GLOBAL AVERAGE METRICS:")
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
