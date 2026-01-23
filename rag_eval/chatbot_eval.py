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

# =========================
# RAGAS
# =========================
from ragas import SingleTurnSample
from ragas.metrics import AnswerRelevancy, ContextRelevance, Faithfulness
from ragas.llms import LangchainLLMWrapper
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

# =========================
# Backend
# =========================
from src.llm.objects.LLMs import Models
from src.llm.assistant import KICampusAssistant
from src.llm.objects.contextualizer import Contextualizer
from src.llm.tools.retrieve import get_retriever


# =====================================================
# CONTEXT RETRIEVAL (NEW LOGIC)
# =====================================================

def _retrieve_context(question: str):
    contextualizer = Contextualizer()
    retriever = get_retriever(use_hybrid=True, n_chunks=5)

    rag_query = contextualizer.contextualize(
        query=question,
        chat_history=[],
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

    # Precision guard 
    if len(contexts) < 2:
        return ()

    return tuple(contexts[:3])


@lru_cache(maxsize=None)
def get_context(question: str):
    """Caches retrieval + contextualization only."""
    return _retrieve_context(question)


# =====================================================
# ANSWER GENERATION (CONTEXT-GROUNDED)
# =====================================================

def generate_answer(question: str, contexts: tuple[str, ...]):
    assistant = KICampusAssistant()

    context_block = "\n\n".join(
        f"[Context {i+1}]\n{c}" for i, c in enumerate(contexts)
    )

    grounded_prompt = (
    "Beantworte die folgende Frage ausschließlich mit den Informationen aus dem untenstehenden Kontext.\n"
    "Falls der Kontext nicht ausreicht, sage dies explizit.\n\n"
    "Kontext:\n"
    f"{context_block}\n\n"
    "Frage:\n"
    f"{question}"
  )


    response, _ = assistant.chat(
        query=grounded_prompt,
        model=Models.GPT4,
    )

    return response.content

# =====================================================
# MAIN EVALUATION
# =====================================================

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
        #single_hop_rag
        "Was bedeutet die Definition KI im Mittelstand?",
        "Was ist erklärbarer KI (XAI)?",
        "Was ist die Markov-Annahme?",
        "Wie arbeitet die Lernmethode Artificial Neural Networks (ANN)?",
        "Welche Vorteile bietet der Einsatz von KI in der öffentlichen Verwaltung?",
        "Warum ist Data Awareness wichtig?",
        "Könntest du erklären, was Embeddings sind und wie sie verwendet werden?",
        "Was ist der Unterschied zwischen Supervised und Unsupervised Learning?",
        "Was ist KI und Ethik?",
        "Welche Arten des Lernens werden im Maschinellen Lernen unterschieden?",
        "Wie funktionieren neuronale Netze?",
        "Was bedeutet Fair AI?",
        "Welche Ziele verfolgt der EU AI Act?",
        "Was bedeutet Clustering?",
        "Was versteht man unter Datenvorverarbeitung im Machine Learning?",
        "Was sind Trainingsdaten bei KI-Modellen?",
        "Was sind die Hauptphasen des Datenlebenszyklus?",
        "Was versteht man unter Learning Analytics?",

        #multi_hop_rag
        "Wie wird der Zusammenhang zwischen Künstlicher Intelligenz und Robot Learning in den KI-Campus-Lernmaterialien erklärt?", 
        "Was ist GANs und wie funktionieren Neuronale Netze?", 
        "Wie beeinflusst Data Science den medizinischen Bereich?",
        "Wie beeinflusst Data Awareness die Qualität von Machine-Learning-Modellen?",
        "Welche Rolle spielt KI-Didaktik in der Hochschullehre?",
        "Welche Grundkonzepte des Maschinellen Lernens werden in KI-Campus-Kursen vermittelt?",
        "Wie hängen LLMs und Chatbots zusammen?",
        "Was sind die Unterschiede zwischen Vektorisierung und Textvorverarbeitung?",
        "Gibt es einen Unterschied zwischen Automated Machine Learning und Machine Learning?",
        "Wie unterscheiden sich Data Literacy und AI Literacy im Bildungskontext?",
        "Welche Faktoren beeinflussen die Antwortqualität großer Sprachmodelle?",
        "Wie kann KI zur Erreichung der Ziele für nachhaltige Entwicklung beitragen?",
        "Welche datenschutzrechtlichen Herausforderungen entstehen beim Einsatz von KI in Medizin?",

        # 2. TECHNISCHER SUPPORT (10)
        #single_hop_rag
        "Wo befindet sich der Prompt-Katalog auf der KI-Campus-Plattform?",
        "Wie funktioniert die Registrierung auf dem KI-Campus?",
        "Wie kann ich meinen Namen ändern?",
        "In welcher Sprache kannst du antworten?",
        "Wie kann man das Benutzerprofil auf der KI-Campus-Plattform bearbeiten?",

        #multi_hop_rag
        "Welche Einstellungen oder Bedingungen sind wichtig, um Plattforminhalte vollständig nutzen zu können?",
        "Welche Ursachen kann es haben, wenn nach dem Zurücksetzen des Passworts keine E-Mail ankommt?",
        "Welche möglichen Ursachen gibt es, wenn 'Meine Kurse' nicht aufgerufen werden kann?",
        "Welche Schritte sollte man durchführen, wenn der Login auf der KI-Campus-Plattform trotz korrekter Zugangsdaten nicht funktioniert?",
        "Was kann man tun, wenn man einen Referenzlink anklickt, aber keinen Zugriff auf den verlinkten Inhalt hat, und welche möglichen Ursachen gibt es dafür?",

        # 3. KURSMODALITÄTEN (10)
        #single_hop_rag
        "Wann erhält man einen Leistungsnachweis?",
        "Welche Funktionen haben Badges auf dem KI-Campus?",
        "Wird die Punktzahl auf dem Zertifikat angezeigt?",
        "Welche Informationen enthält eine Teilnahmebestätigung?",
        "Für welche Kurse wird ein Micro-Degree angeboten?",

        #multi_hop_rag
        "Welche Voraussetzungen müssen für den erfolgreichen Abschluss eines KI-Campus-Kurses erfüllt sein und wie hängen diese zusammen?",
        "Welche Rolle spielen Übungsaufgaben und Quizformate für den erfolgreichen Abschluss eines KI-Campus-Kurses?",
        "Worin unterscheiden sich Teilnahmebestätigung, Leistungsnachweis und Zertifikat auf dem KI-Campus, und wann bekommt man welches Dokument?",
        "Wie hängen Pflichtaufgaben und Bewertung zusammen, wenn man einen KI-Campus-Kurs erfolgreich abschließen möchte?",
        "Wie wirken sich Quizversuche und der eigene Lernfortschritt auf den Erhalt von Leistungsnachweisen aus?",
        
        # 4. ANFRAGEN ZUR CHATBOTFUNKTION (10)
        #single_hop_rag
        "Stellt der KI-Campus Podcasts zur Verfügung?",
        "Gibt es Quizformate auf der Plattform zur Selbstüberprüfung?",
        "Beantwortet der Chatbot ausschließlich Fragen zu KI-Themen?",
        "Was ist der Zweck der KI-Campus-Plattform?",
        "Welche funktionalen Einschränkungen hat der Chatbot?",

        #multi_hop_rag
        "Wie nutzt der Chatbot bereitgestellte Dokumente zur Beantwortung von Fragen?",
        "Welche Strategien nutzt der Chatbot, wenn eine Frage nicht eindeutig beantwortbar ist?",
        "Wie ist der KI-Campus-Chatbot technisch aufgebaut?",
        "Was macht der Chatbot, wenn eine Frage unklar gestellt ist oder mehrere mögliche Antworten zulässt?",
        "Was passiert, wenn der KI-Campus-Chatbot eine Frage nicht beantworten kann, und welche Gründe können dafür zusammenkommen?",
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

            answer = generate_answer(q, contexts)

            print("\nAnswer:\n")
            print(answer)

            sample = SingleTurnSample(
                user_input=q,
                response=answer,
                retrieved_contexts=list(contexts),
            )

            for m in metrics:
                score = float(await m.single_turn_ascore(sample))
                per_question_metric_sums[m.name] += score
                global_metric_sums[m.name] += score
                print(f"  - {m.name}: {score:.3f}")

            runs.append({
                "run": run_idx + 1,
                "answer": answer,
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
