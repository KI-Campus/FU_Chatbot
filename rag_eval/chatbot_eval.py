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
        #single_hop_rag (16)
        "Was versteht man unter maschinelles lernen",
        "was ist erklärbarer KI (XAI)",
        "Wie funktionieren Neuronale Netze",
        "Wie funktioniert das Grdientenverfahren?",
        "Why is data awareness important?",
        "Could you explain what embeddings are and how they are used?",
        "Welche Artikel des EU AI Act sind relevant für die Risikoklasse inakzeptables Risiko?",
        "Wie arbeitet die Lernmethode ANN",
        "welche Plichten haben Betreiber?",
        "Wie funktionieren neuronale Netze?",
        "Was bedeutet "Inferieren"?",
        "Welche Ziele verfolgt der EU AI Act?",
        "Welche LLM-Version nutz Copilot aktuell?",
        "Was sind Transformer",
        "Was ist Lava?",
        "What are the main phases of the data lifecycle?",
        "Was ist nicht parametrische Statistik?",

        # 2. no vector db quatsch (14)
        "Erstelle ein viedeo wo ein Pferd ein Salto macht", 
        "Wie heisst ist der erdkern?", 
        "Du bist aber ziemlich dämlich. Wie soll ich denn hier anständig was lernen?",
        "Wie ist das Wetter?",
        "blurr",
        "test",
        "test test test",
        "C😝😙🤑😊☺️😊😗😊☺️😊😝😊😝😊☺️😊☺️", 
        "Magst du Nudeln?", 
        "du hast schon zwei bier getrunken",
        "Sommerabend im Tiergarten das Gedicht aus 1916 was für ein reimschema ist das",
        "Ich habe Hunger.",
        "Ich binn auch eine ki",
        "Du bist nutzlos"

        # 2. TECHNISCHER SUPPORT (15)
        #single_hop_rag
        "Wie kann ich meinen Namen ändern?",
        "what are the costs of a course?",
        "Welchen Kurs kannst du empfehlen?",
        "Was kann man tun, wenn die Fehlermeldung 'The Vimeo video could not be loaded' erscheint?",
        "Wie kann man das Benutzerprofil auf der KI-Campus-Plattform bearbeiten?",
        "Welchen Einsteigerkurs",
        "Ich möchte Prompting lernen",
        "Gibt es Bescheinigungen",
        "Wo finde ich Ansprachpartner?",

        #multi_hop_rag
        "Ich bin Student und möchte lernen",
        "Ich bin Schüler und möchte lernen",
        "Ich arbeite in der Verwaltung, was kannst du empfehlen?",
        "Welche Schritte sollte man durchführen, wenn der Login auf der KI-Campus-Plattform trotz korrekter Zugangsdaten nicht funktioniert?",
        "Was kann man tun, wenn man einen Referenzlink anklickt, aber keinen Zugriff auf den verlinkten Inhalt hat, und welche möglichen Ursachen gibt es dafür?",
        "Ich komme von der HU und möchte Credits",
        

        # 3. KURSMODALITÄTEN (15)
        #single_hop_rag
        "Wann erhält man einen Leistungsnachweis?",
        "Welche Funktionen haben Badges auf dem KI-Campus?",
        "Wird die Punktzahl auf dem Zertifikat angezeigt?",
        "Welche Informationen enthält eine Teilnahmebestätigung?",
        "Für welche Kurse wird ein Micro-Degree angeboten?",
        "wo beginnt Modul 2",
        "how does certification work?",
        "Wann bekomme ich meine Teilnahmebescheinigung?",
        "Gibt es ein Zertifikat?",
        "Wie lange geht der Kurs?",
        "Kann ich den Kurs ohne Speichern abbrechen und später an derselben Stelle weitermachen?",
        "Was ist Moodle",
        "Wie bekomme ich Credits",
        "Kann der Chatbot bei der Erstellung eines eigenen Chatbots helfen?",
        "Was sind badges",
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
