"""
Test-Skript für die OpenWebUI Arena API.

Dieses Skript testet beide Chatbot-Versionen und vergleicht ihre Antworten.
"""

import asyncio
import json
from typing import Any

import httpx


API_BASE_URL = "http://localhost:8001"


async def test_health() -> dict[str, Any]:
    """Teste den Health-Endpoint."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/health")
        assert response.status_code == 200
        return response.json()


async def test_list_models() -> dict[str, Any]:
    """Liste alle verfügbaren Modelle."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) >= 2
        return data


async def test_chat_completion(model: str, query: str) -> dict[str, Any]:
    """Teste Chat Completion für ein spezifisches Modell."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{API_BASE_URL}/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": query}],
                "stream": False,
            },
        )
        assert response.status_code == 200
        return response.json()


async def compare_models(query: str) -> None:
    """Vergleiche die Antworten beider Modelle für die gleiche Frage."""
    print(f"\n{'=' * 80}")
    print(f"Frage: {query}")
    print(f"{'=' * 80}\n")

    # Test Original-Version
    print("🤖 Original-Version (kicampus-original):")
    print("-" * 80)
    original_response = await test_chat_completion("kicampus-original", query)
    original_answer = original_response["choices"][0]["message"]["content"]
    print(original_answer)
    print()

    # Test Verbesserte Version
    print("🚀 Verbesserte Version (kicampus-improved):")
    print("-" * 80)
    improved_response = await test_chat_completion("kicampus-improved", query)
    improved_answer = improved_response["choices"][0]["message"]["content"]
    print(improved_answer)
    print()

    # Vergleich
    print("📊 Vergleich:")
    print("-" * 80)
    print(f"Original Länge: {len(original_answer)} Zeichen")
    print(f"Verbessert Länge: {len(improved_answer)} Zeichen")
    print()


async def main():
    """Hauptfunktion zum Testen der API."""
    print("🧪 Starte Tests für OpenWebUI Arena API\n")

    # Test 1: Health Check
    print("1️⃣ Teste Health Endpoint...")
    health = await test_health()
    print(f"✅ Health Check: {health}\n")

    # Test 2: List Models
    print("2️⃣ Teste Model Listing...")
    models = await test_list_models()
    print(f"✅ Verfügbare Modelle: {[m['id'] for m in models['data']]}\n")

    # Test 3: Vergleiche Modelle mit verschiedenen Fragen
    test_queries = [
        "Was ist Deep Learning?",
        "Erkläre mir den Unterschied zwischen KI und Machine Learning.",
        "Welche Kurse gibt es auf KI-Campus zum Thema Ethik?",
    ]

    for query in test_queries:
        await compare_models(query)

    print(f"\n{'=' * 80}")
    print("✅ Alle Tests erfolgreich abgeschlossen!")
    print(f"{'=' * 80}\n")


if __name__ == "__main__":
    asyncio.run(main())
