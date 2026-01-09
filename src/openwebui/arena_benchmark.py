#!/usr/bin/env python3
"""
Chatbot Arena Benchmark Tool

Vergleicht zwei Chatbot-Versionen (Original vs. Improved) mit identischen Fragen.
Alternative zu OpenWebUI Arena Mode.
"""

import json
import time
from typing import List, Dict
import requests


API_BASE_URL = "http://localhost:8001/v1"


def chat(model: str, message: str, history: List[Dict] = None) -> Dict:
    """Sendet eine Chat-Anfrage an die API."""
    messages = history or []
    messages.append({"role": "user", "content": message})
    
    response = requests.post(
        f"{API_BASE_URL}/chat/completions",
        json={"model": model, "messages": messages},
        timeout=60
    )
    response.raise_for_status()
    return response.json()


def format_response(response: Dict) -> str:
    """Formatiert die API-Response für die Anzeige."""
    return response["choices"][0]["message"]["content"]


def compare_models(question: str) -> None:
    """Vergleicht beide Modelle mit der gleichen Frage."""
    print("\n" + "=" * 80)
    print(f"❓ FRAGE: {question}")
    print("=" * 80)
    
    # Test Original Model
    print("\n🤖 KICAMPUS-ORIGINAL:")
    print("-" * 80)
    start = time.time()
    response_original = chat("kicampus-original", question)
    time_original = time.time() - start
    answer_original = format_response(response_original)
    print(answer_original)
    print(f"\n⏱️  Antwortzeit: {time_original:.2f}s")
    
    # Test Improved Model
    print("\n🚀 KICAMPUS-IMPROVED:")
    print("-" * 80)
    start = time.time()
    response_improved = chat("kicampus-improved", question)
    time_improved = time.time() - start
    answer_improved = format_response(response_improved)
    print(answer_improved)
    print(f"\n⏱️  Antwortzeit: {time_improved:.2f}s")
    
    # Statistik
    print("\n" + "=" * 80)
    print("📊 VERGLEICH:")
    print(f"Original: {len(answer_original)} Zeichen, {time_original:.2f}s")
    print(f"Improved: {len(answer_improved)} Zeichen, {time_improved:.2f}s")
    print("=" * 80 + "\n")


def run_benchmark():
    """Führt einen vollständigen Benchmark durch."""
    print("=" * 80)
    print("🏆 CHATBOT ARENA BENCHMARK")
    print("=" * 80)
    print("\nVergleiche: kicampus-original vs. kicampus-improved\n")
    
    # Test-Fragen
    questions = [
        "Was ist Künstliche Intelligenz?",
        "Erkläre Deep Learning in einfachen Worten",
        "Welche Kurse bietet KI-Campus an?",
        "Was ist der Unterschied zwischen Machine Learning und KI?",
        "Wie funktioniert ein neuronales Netzwerk?",
    ]
    
    for i, question in enumerate(questions, 1):
        print(f"\n{'='*80}")
        print(f"Test {i}/{len(questions)}")
        compare_models(question)
        
        if i < len(questions):
            input("⏸️  Drücke Enter für die nächste Frage...")
    
    print("\n" + "=" * 80)
    print("✅ BENCHMARK ABGESCHLOSSEN!")
    print("=" * 80 + "\n")


def interactive_mode():
    """Interaktiver Modus zum manuellen Testen."""
    print("=" * 80)
    print("💬 INTERAKTIVER VERGLEICHSMODUS")
    print("=" * 80)
    print("\nGib deine Fragen ein (leer = beenden)\n")
    
    while True:
        question = input("❓ Deine Frage: ").strip()
        if not question:
            break
        
        compare_models(question)


def main():
    """Hauptfunktion."""
    print("\n🎯 KI-Campus Chatbot Arena\n")
    print("Wähle einen Modus:")
    print("1. Automatischer Benchmark (5 vordefinierte Fragen)")
    print("2. Interaktiver Modus (eigene Fragen)")
    print("3. Einzelne Frage")
    
    choice = input("\nDeine Wahl (1-3): ").strip()
    
    if choice == "1":
        run_benchmark()
    elif choice == "2":
        interactive_mode()
    elif choice == "3":
        question = input("\n❓ Deine Frage: ").strip()
        if question:
            compare_models(question)
    else:
        print("❌ Ungültige Wahl")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Abgebrochen\n")
    except requests.exceptions.ConnectionError:
        print("\n❌ Fehler: API ist nicht erreichbar. Läuft der Server auf Port 8001?\n")
    except Exception as e:
        print(f"\n❌ Fehler: {e}\n")
