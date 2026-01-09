#!/usr/bin/env python3
"""
Arena Benchmark Tool - Vergleicht zwei Modelle side-by-side über die REST API.
Keine WebUI notwendig - alles läuft im Terminal mit schöner Formatierung.
"""

import requests
import json
import time
from typing import Dict, List
from datetime import datetime

# Konfiguration
API_BASE_URL = "http://localhost:8001"
MODELS = ["kicampus-original", "kicampus-improved"]

# ANSI Farben für Terminal
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[95m'
    BLUE = '\033[94m'
    GRAY = '\033[90m'


def print_header(title: str):
    """Druckt einen formatierten Header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{title.center(80)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}\n")


def print_model_section(model_name: str, is_original: bool):
    """Druckt einen Modell-Header."""
    label = "ORIGINAL" if is_original else "VERBESSERT"
    color = Colors.GREEN if is_original else Colors.MAGENTA
    print(f"{Colors.BOLD}{color}[{label}] {model_name}{Colors.RESET}")


def query_model(model: str, query: str, stream: bool = False) -> Dict:
    """Sendet eine Query an ein Modell und gibt die Response zurück."""
    url = f"{API_BASE_URL}/v1/chat/completions"
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": query}],
        "stream": stream
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        start_time = time.time()
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            answer = data["choices"][0]["message"]["content"]
            
            # Entferne die Mock-Präfixe für cleaner Output
            if answer.startswith("[Original]"):
                answer = answer.replace("[Original] ", "")
            elif answer.startswith("[Verbessert]"):
                answer = answer.replace("[Verbessert] ", "")
            
            return {
                "status": "success",
                "answer": answer,
                "time": elapsed,
                "tokens": {
                    "prompt": data["usage"]["prompt_tokens"],
                    "completion": data["usage"]["completion_tokens"]
                }
            }
        else:
            return {"status": "error", "error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def format_answer(answer: str, max_length: int = 150) -> str:
    """Formatiert die Antwort für die Anzeige."""
    if len(answer) > max_length:
        return answer[:max_length] + "..."
    return answer


def compare_models(query: str):
    """Vergleicht die Antworten beider Modelle."""
    print(f"\n{Colors.BOLD}{Colors.YELLOW}FRAGE:{Colors.RESET} {query}\n")
    
    results = {}
    
    # Query beide Modelle parallel (sequenziell für Einfachheit)
    for i, model in enumerate(MODELS):
        is_original = (i == 0)
        print_model_section(model, is_original)
        
        result = query_model(model, query)
        results[model] = result
        
        if result["status"] == "success":
            print(f"Antwort: {format_answer(result['answer'])}")
            print(f"⏱️  Zeit: {result['time']:.2f}s | 📊 Tokens: {result['tokens']['completion']} Completion")
        else:
            print(f"{Colors.RED}❌ Fehler: {result['error']}{Colors.RESET}")
        
        print()
    
    # Vergleich
    print(f"{Colors.BOLD}{Colors.BLUE}{'─'*80}{Colors.RESET}")
    print(f"{Colors.BOLD}📊 VERGLEICH:{Colors.RESET}\n")
    
    if results["kicampus-original"]["status"] == "success" and results["kicampus-improved"]["status"] == "success":
        orig_time = results["kicampus-original"]["time"]
        imp_time = results["kicampus-improved"]["time"]
        orig_tokens = results["kicampus-original"]["tokens"]["completion"]
        imp_tokens = results["kicampus-improved"]["tokens"]["completion"]
        
        print(f"Original Antwort-Länge:  {len(results['kicampus-original']['answer'])} Zeichen")
        print(f"Improved Antwort-Länge: {len(results['kicampus-improved']['answer'])} Zeichen")
        print(f"Länge-Unterschied: {abs(len(results['kicampus-improved']['answer']) - len(results['kicampus-original']['answer']))} Zeichen")
        print()
        print(f"Original Antwort-Zeit:  {orig_time:.2f}s")
        print(f"Improved Antwort-Zeit: {imp_time:.2f}s")
        print(f"Zeit-Unterschied: {abs(imp_time - orig_time):.2f}s")


def interactive_mode():
    """Interaktiver Modus für Fragen."""
    print_header("🤖 KI-Campus Arena Benchmark - Interaktiver Modus")
    
    while True:
        print(f"{Colors.YELLOW}Gib eine Frage ein (oder 'exit' zum Beenden):{Colors.RESET}")
        query = input("> ").strip()
        
        if query.lower() == "exit":
            print(f"\n{Colors.GREEN}Auf Wiedersehen! 👋{Colors.RESET}\n")
            break
        
        if query:
            compare_models(query)
            print("\n" + "─"*80)


def batch_mode(questions: List[str]):
    """Batch Modus für vordefinierte Fragen."""
    print_header("🤖 KI-Campus Arena Benchmark - Batch Mode")
    print(f"Führe {len(questions)} Fragen aus...\n")
    
    for i, question in enumerate(questions, 1):
        print(f"{Colors.YELLOW}[{i}/{len(questions)}]{Colors.RESET}")
        compare_models(question)
        print("─"*80)
        time.sleep(0.5)  # Kleine Pause zwischen Fragen


def check_api_health():
    """Prüft ob die API erreichbar ist."""
    try:
        response = requests.get(f"{API_BASE_URL}/", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"{Colors.GREEN}✅ API ist erreichbar!{Colors.RESET}")
            print(f"   Service: {data.get('service')}")
            print(f"   Modelle: {', '.join(data.get('available_models', []))}\n")
            return True
        else:
            print(f"{Colors.RED}❌ API antwortet mit Status {response.status_code}{Colors.RESET}\n")
            return False
    except Exception as e:
        print(f"{Colors.RED}❌ API nicht erreichbar: {str(e)}{Colors.RESET}")
        print(f"   Prüfe: export KEY_VAULT_NAME='kicwa-keyvault-lab'")
        print(f"   Dann: /Users/browse/.pyenv/versions/3.11.7/bin/python -m uvicorn src.openwebui.openwebui_api_simple:app --host 0.0.0.0 --port 8001\n")
        return False


def main():
    """Hauptprogramm."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("╔════════════════════════════════════════════════════════════════════════════════╗")
    print("║     KI-Campus Chatbot Arena Mode Benchmark Tool                              ║")
    print("║     Vergleiche zwei Versionen des Chatbots side-by-side                       ║")
    print("╚════════════════════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.RESET}\n")
    
    # Prüfe API Health
    if not check_api_health():
        return
    
    # Vordefinierte Testfragen
    test_questions = [
        "Was ist Künstliche Intelligenz?",
        "Erkläre Machine Learning in 2 Sätzen",
        "Was sind Neural Networks?",
        "Wie funktioniert Deep Learning?",
        "Nenne 3 Anwendungen von KI",
    ]
    
    print(f"{Colors.BOLD}Wähle einen Modus:{Colors.RESET}")
    print("1) Interaktiv (Fragen eingeben)")
    print("2) Batch (Vordefinierte Fragen)")
    print("3) Single Query (Eine Frage)")
    print("4) Exit")
    
    choice = input(f"\n{Colors.YELLOW}Deine Wahl (1-4):{Colors.RESET} ").strip()
    
    if choice == "1":
        interactive_mode()
    elif choice == "2":
        batch_mode(test_questions)
    elif choice == "3":
        print(f"\n{Colors.YELLOW}Gib eine Frage ein:{Colors.RESET}")
        query = input("> ").strip()
        if query:
            compare_models(query)
    elif choice == "4":
        print(f"\n{Colors.GREEN}Auf Wiedersehen! 👋{Colors.RESET}\n")
    else:
        print(f"{Colors.RED}Ungültige Wahl!{Colors.RESET}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Unterbrochen.{Colors.RESET}")
