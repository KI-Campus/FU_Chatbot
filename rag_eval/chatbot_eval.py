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
from src.llm.objects.question_answerer import QuestionAnswerer
from src.llm.tools.contextualize import get_contextualizer
from src.llm.tools.retrieve import get_retriever
from src.llm.objects.reranker import Reranker
from eval_decompose import decompose_query_eval
from rag_eval.eval_retrieve_multi import retrieve_multi_parallel_eval
from src.llm.objects.citation_parser import CitationParser
from rag_eval.eval_synthesizer import synthesize_answer_eval

course_ids = [1, 6, 10, 19, 27, 28, 29, 36, 37, 38, 41, 43, 44, 46, 48, 49, 50, 51, 53, 55, 56, 57, 58, 59, 60, 63, 64, 66, 67, 74, 75, 76, 78, 79, 80, 88, 92, 93, 95, 98, 99, 100, 103, 106, 107, 109, 111, 121, 124, 127, 128, 134, 136, 140, 141, 142, 143, 144, 145, 151, 152, 153, 158, 160, 161, 163, 164, 165, 168, 171, 176, 177, 180, 185, 186, 187, 190, 191, 192, 197, 198, 199, 202, 203, 213, 214, 215, 221, 223, 224, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 241, 242, 243, 245, 248, 249, 250, 251, 252, 253, 255, 256, 257, 258, 259, 266, 267, 268, 270, 271, 272, 274, 275, 276, 279, 282, 283, 284, 285, 286, 287, 289, 290, 291, 293, 294, 295, 296, 297, 301, 304, 305, 311, 313, 316, 317, 318, 319, 320, 321, 322, 323, 325, 329, 330, 331, 332, 334, 335, 337, 338, 340, 341, 342, 349, 350, 351, 352, 353, 354, 355, 356, 357, 358, 359, 360, 362, 363, 364, 365, 367, 369, 370, 372, 373, 374, 385, 386, 387, 390, 397]

# =====================================================
# CONTEXT RETRIEVAL (NEW LOGIC)
# =====================================================

def answer_question(question: str, course_id: int) -> tuple[str, ...]:
    retrieve_top_n = 10
    contextualizer = get_contextualizer()
    retriever = get_retriever(use_hybrid=True, n_chunks=retrieve_top_n)
    reranker = Reranker(top_n=5)
    question_answerer = QuestionAnswerer()
    citation_parser = CitationParser()

    if course_id is None:
        is_moodle = False
    else:
        is_moodle = True

    mode = contextualizer.classify_scenario(query=question, model=Models.GPT4)

    if mode == "multi_hop":
        decomposed = decompose_query_eval(model=Models.GPT4, query=question)
        retrieved_nodes = retrieve_multi_parallel_eval(
            subqueries=decomposed, course_id=course_id, module_id=None, retrieve_top_n=retrieve_top_n
        )
        combined_nodes = synthesize_answer_eval(retrieved_nodes=retrieved_nodes)
        reranked_nodes = reranker.rerank(query=question, nodes=combined_nodes, model=Models.GPT4)
    else:
        retrieved_nodes = retriever.retrieve(query=question,course_id=course_id, module_id=None)
        reranked_nodes = reranker.rerank(query=question, nodes=retrieved_nodes, model=Models.GPT4)

    contexts = []
    for node in reranked_nodes:
        try:
            contexts.append(node.text)
        except Exception as e:
            logger.error(f"Failed to extract content from node: {e}")

    response = question_answerer.answer_question(
        query=question,
        chat_history=[],
        sources=reranked_nodes,
        model=Models.GPT4,
        language="German",
        is_moodle=is_moodle,
        course_id=None,
    )

    answer = citation_parser.parse(response.content, source_documents=reranked_nodes)

    return tuple(tuple(contexts), answer)

# =====================================================
# MAIN EVALUATION
# =====================================================

async def main():
    print("\nStarting evaluation...\n")

    evaluator_llm = LangchainLLMWrapper(
        ChatOpenAI(model="gpt-4o", temperature=0)
    )

    embeddings_evaluator_llm = OpenAIEmbeddings(model="text-embedding-3-small")

    metrics = [
        AnswerRelevancy(llm=evaluator_llm, embeddings=embeddings_evaluator_llm),
        ContextRelevance(llm=evaluator_llm),
        Faithfulness(llm=evaluator_llm),
    ]

    # --------------------------------------------------
    # Evaluation Questions
    # --------------------------------------------------
    moodle_questions = [
        # 1. WISSEN ALLGEMEIN & KURSBEZOGEN
        #simple_hop_rag
        "Was ist erklärbarer KI (XAI)?",
        "Was bedeutet der Begriff Prompt in KI-Systemen?",
        "Welche Vorteile bietet der Einsatz von KI in der öffentlichen Verwaltung?",
        "Warum ist Data Awareness wichtig?",
        "Kannst du mir 3 podcasts zu Künstlicher Intelligenz empfehlen?",
        "Wie arbeitet die Lernmethode Artificial Neural Networks (ANN)?",
        "Was ist der Unterschied zwischen Supervised und Unsupervised Learning?",
        "Was ist KI und Ethik?",
        "Welche Arten des Lernens werden im Maschinellen Lernen unterschieden?",
        "Wie funktionieren neuronale Netze?",
        "Warum ist Ethik bei KI wichtig?",
        "Welche Ziele verfolgt der EU AI Act?",
        "Was bedeutet Clustering?",
        "Was ist Reinforcement Learning?",
        "Was sind Trainingsdaten bei KI-Modellen?",
        "Was sind die Hauptphasen des Datenlebenszyklus?",
        "Was versteht man unter Learning Analytics?",

        #multi_hop_rag
        "Wie hängen Künstliche Intelligenz und Robotik zusammen?",
        "Was ist GANs und wie funktionieren Neuronale Netze?",
        "Wie beeinflusst Data Science den medizinischen Bereich?",
        "Wie beeinflusst Data Awareness die Qualität von Machine-Learning-Modellen?",
        "Welche Rolle spielt KI-Didaktik in der Hochschullehre?",
        "Welche Grundkonzepte des Maschinellen Lernens werden in KI-Campus-Kursen vermittelt?",
        "Wie hängen LLMs und Chatbots zusammen?",
        "Was sind k-NN und Regression?",
        "Gibt es einen Unterschied zwischen Automated Machine Learning und Machine Learning?",
        "Wie unterscheiden sich Data Literacy und AI Literacy im Bildungskontext?",
        "Welche Faktoren beeinflussen die Antwortqualität großer Sprachmodelle?",
        "Wie kann KI zur Erreichung der Ziele für nachhaltige Entwicklung beitragen?",
        "Welche datenschutzrechtlichen Herausforderungen entstehen beim Einsatz von KI in Medizin?"]
    
    questions = [

        # 1. WISSEN ALLGEMEIN & KURSBEZOGEN (30)
        #simple_hop_rag
        "Was ist Overfitting?",
        "Was ist erklärbarer KI (XAI)?",
        "Was bedeutet der Begriff Prompt in KI-Systemen?",
        "Welche Vorteile bietet der Einsatz von KI in der öffentlichen Verwaltung?",
        "Warum ist Data Awareness wichtig?",
        "Wie arbeitet die Lernmethode Artificial Neural Networks (ANN)?",
        "Was ist der Unterschied zwischen Supervised und Unsupervised Learning?",
        "Was ist KI und Ethik?",
        "Welche Arten des Lernens werden im Maschinellen Lernen unterschieden?",
        "Wie funktionieren neuronale Netze?",
        "Warum ist Ethik bei KI wichtig?",
        "Welche Ziele verfolgt der EU AI Act?",
        "Was bedeutet Clustering?",
        "Was sind Testdaten?",
        "Was sind Trainingsdaten bei KI-Modellen?",
        "Was sind die Hauptphasen des Datenlebenszyklus?",
        "Was versteht man unter Learning Analytics?",

        #multi_hop_rag
        "Wie hängen Künstliche Intelligenz und Robotik zusammen?", 
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
        #simple_hop_rag
        "Wo befindet sich der Prompt-Katalog auf der KI-Campus-Plattform?",
        "Wie funktioniert die Registrierung auf dem KI-Campus?",
        "Wie kann ich meinen Namen ändern?",
        "In welcher Sprache kannst du antworten?",
        "Wie kann man das Benutzerprofil auf der KI-Campus-Plattform bearbeiten?",
        "Welche Voraussetzungen muss ich erfüllen, um alle Plattforminhalte nutzen zu können?",
        "Was kann ich tun, wenn ich nach dem Zurücksetzen des Passworts keine E-Mail erhalte?",
        "Wo finde ich den Bereich 'Meine Kurse'?",
        "Wie kann ich ein Konto auf der KI-Campus-Website erstellen?",
        "Was kann ich tun, wenn ich trotz eines Referenzlinks keinen Zugriff auf Inhalte habe?",

        # 3. KURSMODALITÄTEN (10)
        #simple_hop_rag
        "Wann erhält man einen Leistungsnachweis?",
        "Welche Funktionen haben Badges auf dem KI-Campus?",
        "Wie bekomme ich Credits?",
        "Welche Informationen enthält eine Teilnahmebestätigung?",
        "Für welche Kurse wird ein Micro-Degree angeboten?",

        #multi_hop_rag
        "Welche Voraussetzungen müssen für den erfolgreichen Abschluss eines KI-Campus-Kurses erfüllt sein und wie hängen diese zusammen?",
        "Welche Rolle spielen Übungsaufgaben und Quizformate für den erfolgreichen Abschluss eines KI-Campus-Kurses?",
        "Worin unterscheiden sich Teilnahmebestätigung, Leistungsnachweis und Zertifikat auf dem KI-Campus, und wann bekommt man welches Dokument?",
        "Wie hängen Pflichtaufgaben und Bewertung zusammen, wenn man einen KI-Campus-Kurs erfolgreich abschließen möchte?",
        "Wie wirken sich Quizversuche und der eigene Lernfortschritt auf den Erhalt von Leistungsnachweisen aus?",
        
        # 4. ANFRAGEN ZUR CHATBOTFUNKTION (10)
        #simple_hop_rag
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

        runs = []

        for run_idx in range(N_REPEATS):
            print(f"\n--- Run {run_idx + 1}/{N_REPEATS} ---")
            # Bei den Moodle Fragen muss course_id = course_ids gesetzt werden
            # Bei den Drupal Fragen muss course_id = None gesetzt werden
            if q in moodle_questions:
                contexts, answer = answer_question(q, course_id = course_ids)
            else:
                contexts, answer = answer_question(q, course_id = None)

            print("\nRetrieved Contexts (first 2):")
            for c in list(contexts)[:2]:
                print("-", c[:250], "...")

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
