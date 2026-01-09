#!/usr/bin/env python3
"""
Arena Voting CLI Tool

Ermöglicht das Durchführen von Arena-Vergleichen zwischen zwei Chatbot-Versionen
mit anschließendem Voting.

Usage:
    python arena_voting.py                    # Interaktiver Modus
    python arena_voting.py --stats            # Zeige Statistiken
    python arena_voting.py --export results.json   # Exportiere alle Votes
"""

import argparse
import json
import sys
import uuid
from datetime import datetime
from typing import Literal, Optional

import requests

# API Base URL
API_BASE = "http://localhost:8001"

# ANSI Color Codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


def print_header(text: str):
    """Prints a colored header."""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'=' * 80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text.center(80)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'=' * 80}{Colors.END}\n")


def print_model_answer(model_name: str, answer: str, label: str):
    """Prints a model's answer with nice formatting."""
    print(f"{Colors.BOLD}{Colors.CYAN}[{label}] {model_name}{Colors.END}")
    print(f"{Colors.BLUE}{'-' * 80}{Colors.END}")
    print(answer)
    print(f"{Colors.BLUE}{'-' * 80}{Colors.END}\n")


def ask_question(question: str, model: str = "kicampus-original") -> str:
    """Fragt ein Modell via API und gibt die Antwort zurück."""
    try:
        response = requests.post(
            f"{API_BASE}/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": question}],
                "stream": False
            },
            timeout=60
        )
        response.raise_for_status()
        
        data = response.json()
        return data["choices"][0]["message"]["content"]
    
    except requests.exceptions.RequestException as e:
        print(f"{Colors.RED}Error querying {model}: {e}{Colors.END}")
        return f"[ERROR: Could not get answer from {model}]"


def save_comparison(question: str, model_a: str, answer_a: str, model_b: str, answer_b: str) -> Optional[str]:
    """Speichert einen Vergleich via API und gibt die comparison_id zurück."""
    try:
        response = requests.post(
            f"{API_BASE}/arena/save-comparison",
            json={
                "question": question,
                "model_a": model_a,
                "answer_a": answer_a,
                "model_b": model_b,
                "answer_b": answer_b
            }
        )
        response.raise_for_status()
        
        data = response.json()
        return data["comparison_id"]
    
    except requests.exceptions.RequestException as e:
        print(f"{Colors.RED}Error saving comparison: {e}{Colors.END}")
        return None


def submit_vote(comparison_id: str, vote: Literal["A", "B", "tie"], comment: Optional[str] = None) -> bool:
    """Submitted einen Vote via API."""
    try:
        response = requests.post(
            f"{API_BASE}/arena/vote",
            json={
                "comparison_id": comparison_id,
                "vote": vote,
                "comment": comment
            }
        )
        response.raise_for_status()
        return True
    
    except requests.exceptions.RequestException as e:
        print(f"{Colors.RED}Error submitting vote: {e}{Colors.END}")
        return False


def get_statistics():
    """Holt Statistiken von der API."""
    try:
        response = requests.get(f"{API_BASE}/arena/statistics")
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.RequestException as e:
        print(f"{Colors.RED}Error getting statistics: {e}{Colors.END}")
        return None


def export_results(output_file: str):
    """Exportiert alle Comparisons."""
    try:
        response = requests.get(f"{API_BASE}/arena/comparisons")
        response.raise_for_status()
        
        data = response.json()
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data["comparisons"], f, indent=2, ensure_ascii=False)
        
        print(f"{Colors.GREEN}✓ Exported {data['total']} comparisons to {output_file}{Colors.END}")
    
    except Exception as e:
        print(f"{Colors.RED}Error exporting: {e}{Colors.END}")


def interactive_mode():
    """Interaktiver Modus: Frage stellen, Antworten vergleichen, voten."""
    print_header("🏟️  Arena Voting - Interactive Mode")
    
    print(f"{Colors.CYAN}Models:{Colors.END}")
    print(f"  {Colors.BOLD}A:{Colors.END} kicampus-original (10 messages context)")
    print(f"  {Colors.BOLD}B:{Colors.END} kicampus-improved (15 messages context)\n")
    
    # Frage eingeben
    print(f"{Colors.YELLOW}Enter your question (or 'quit' to exit):{Colors.END}")
    question = input("> ").strip()
    
    if question.lower() in ['quit', 'exit', 'q']:
        print(f"{Colors.CYAN}Goodbye!{Colors.END}")
        return
    
    if not question:
        print(f"{Colors.RED}No question provided.{Colors.END}")
        return
    
    print(f"\n{Colors.CYAN}🤖 Querying both models...{Colors.END}\n")
    
    # Beide Modelle fragen
    answer_a = ask_question(question, "kicampus-original")
    answer_b = ask_question(question, "kicampus-improved")
    
    # Antworten anzeigen
    print_header("📝 Comparison Results")
    print(f"{Colors.BOLD}Question:{Colors.END} {question}\n")
    
    print_model_answer("kicampus-original", answer_a, "Model A")
    print_model_answer("kicampus-improved", answer_b, "Model B")
    
    # Comparison speichern
    comparison_id = save_comparison(
        question=question,
        model_a="kicampus-original",
        answer_a=answer_a,
        model_b="kicampus-improved",
        answer_b=answer_b
    )
    
    if not comparison_id:
        print(f"{Colors.RED}Failed to save comparison. Cannot vote.{Colors.END}")
        return
    
    print(f"{Colors.GREEN}✓ Comparison saved (ID: {comparison_id}){Colors.END}\n")
    
    # Vote
    print(f"{Colors.YELLOW}Which answer is better?{Colors.END}")
    print(f"  {Colors.BOLD}A{Colors.END} - Model A (kicampus-original)")
    print(f"  {Colors.BOLD}B{Colors.END} - Model B (kicampus-improved)")
    print(f"  {Colors.BOLD}T{Colors.END} - Tie (both equally good/bad)")
    print(f"  {Colors.BOLD}S{Colors.END} - Skip (don't vote)")
    
    vote_input = input(f"{Colors.YELLOW}Your vote [A/B/T/S]:{Colors.END} ").strip().upper()
    
    if vote_input == "S":
        print(f"{Colors.CYAN}Vote skipped.{Colors.END}")
        return
    
    vote_map = {"A": "A", "B": "B", "T": "tie"}
    vote = vote_map.get(vote_input)
    
    if not vote:
        print(f"{Colors.RED}Invalid vote. Skipping.{Colors.END}")
        return
    
    # Optional comment
    print(f"{Colors.YELLOW}Optional comment (press Enter to skip):{Colors.END}")
    comment = input("> ").strip()
    comment = comment if comment else None
    
    # Submit vote
    if submit_vote(comparison_id, vote, comment):
        print(f"\n{Colors.GREEN}✓ Vote submitted successfully!{Colors.END}")
        
        # Show updated stats
        stats = get_statistics()
        if stats:
            print(f"\n{Colors.CYAN}Current Statistics:{Colors.END}")
            print(f"  Total Comparisons: {stats['total_comparisons']}")
            print(f"  Voted: {stats['voted']}")
            print(f"  Votes for A: {stats['votes_for_a']} ({stats['win_rate_a']*100:.1f}%)")
            print(f"  Votes for B: {stats['votes_for_b']} ({stats['win_rate_b']*100:.1f}%)")
            print(f"  Ties: {stats['votes_tie']} ({stats['tie_rate']*100:.1f}%)")
    else:
        print(f"{Colors.RED}Failed to submit vote.{Colors.END}")


def show_statistics():
    """Zeigt Statistiken an."""
    print_header("📊 Arena Statistics")
    
    stats = get_statistics()
    if not stats:
        return
    
    print(f"{Colors.BOLD}Total Comparisons:{Colors.END} {stats['total_comparisons']}")
    print(f"{Colors.BOLD}Voted:{Colors.END} {stats['voted']}")
    print(f"{Colors.BOLD}Unvoted:{Colors.END} {stats['unvoted']}")
    print()
    
    if stats['voted'] > 0:
        print(f"{Colors.BOLD}Vote Distribution:{Colors.END}")
        print(f"  Model A wins: {Colors.GREEN}{stats['votes_for_a']}{Colors.END} ({stats['win_rate_a']*100:.1f}%)")
        print(f"  Model B wins: {Colors.GREEN}{stats['votes_for_b']}{Colors.END} ({stats['win_rate_b']*100:.1f}%)")
        print(f"  Ties: {Colors.YELLOW}{stats['votes_tie']}{Colors.END} ({stats['tie_rate']*100:.1f}%)")
        print()
        
        # Winner
        if stats['votes_for_a'] > stats['votes_for_b']:
            winner = "Model A (kicampus-original)"
        elif stats['votes_for_b'] > stats['votes_for_a']:
            winner = "Model B (kicampus-improved)"
        else:
            winner = "Tie"
        
        print(f"{Colors.BOLD}Current Leader:{Colors.END} {Colors.GREEN}{winner}{Colors.END}")
    
    print(f"\n{Colors.BOLD}Models Seen:{Colors.END} {', '.join(stats['models_seen'])}")


def main():
    parser = argparse.ArgumentParser(
        description="Arena Voting CLI Tool for KI-Campus Chatbot Benchmarking"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show voting statistics"
    )
    parser.add_argument(
        "--export",
        type=str,
        metavar="FILE",
        help="Export all comparisons to JSON file"
    )
    
    args = parser.parse_args()
    
    # Check API connectivity
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        response.raise_for_status()
    except Exception as e:
        print(f"{Colors.RED}Error: Cannot connect to API at {API_BASE}{Colors.END}")
        print(f"{Colors.RED}Make sure the API server is running.{Colors.END}")
        print(f"{Colors.YELLOW}Start it with: python -m uvicorn src.openwebui.openwebui_api_llm:app --host 0.0.0.0 --port 8001{Colors.END}")
        sys.exit(1)
    
    # Handle commands
    if args.stats:
        show_statistics()
    elif args.export:
        export_results(args.export)
    else:
        # Interactive mode
        try:
            while True:
                interactive_mode()
                
                print(f"\n{Colors.YELLOW}Continue with another question? [y/N]{Colors.END}")
                cont = input("> ").strip().lower()
                
                if cont not in ['y', 'yes']:
                    print(f"{Colors.CYAN}Goodbye!{Colors.END}")
                    break
        
        except KeyboardInterrupt:
            print(f"\n{Colors.CYAN}Interrupted. Goodbye!{Colors.END}")
            sys.exit(0)


if __name__ == "__main__":
    main()
