"""
OpenWebUI-kompatible API - SIMPLIFIED VERSION mit Streaming-Support für Arena Mode.
"""

import asyncio
import json
import time
from typing import AsyncGenerator, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

app = FastAPI(
    title="KI-Campus Chatbot Arena API (Test Mode)",
    description="OpenWebUI-kompatible API mit Streaming-Support für Arena Mode",
    version="1.0.0-test",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[Message]
    stream: bool = Field(default=False)


class ChatCompletionChoice(BaseModel):
    index: int
    message: Message
    finish_reason: str


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]


class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str


class ModelsResponse(BaseModel):
    object: str = "list"
    data: list[ModelInfo]


@app.get("/")
def root():
    return {
        "status": "online",
        "service": "KI-Campus Chatbot Arena (Test Mode)",
        "available_models": ["kicampus-original", "kicampus-improved"],
        "note": "This is a simplified test version. Replace with full version once dependencies are resolved.",
    }


@app.get("/v1/models")
def list_models() -> ModelsResponse:
    return ModelsResponse(
        data=[
            ModelInfo(id="kicampus-original", created=1700000000, owned_by="ki-campus"),
            ModelInfo(id="kicampus-improved", created=1700000000, owned_by="ki-campus"),
        ]
    )


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """
    OpenAI-kompatible Chat-Completions mit Streaming-Support.
    Wenn stream=True, wird SSE (Server-Sent Events) verwendet.
    """
    
    if request.model not in ["kicampus-original", "kicampus-improved"]:
        raise HTTPException(status_code=400, detail=f"Unknown model: {request.model}")
    
    user_message = request.messages[-1].content if request.messages else ""
    
    # Demo-Antworten basierend auf dem Modell
    if request.model == "kicampus-original":
        response_text = f"[Original] Demo-Antwort auf: '{user_message}'\n\nDies ist die Standard-Version des KI-Campus Chatbots. Um die echten LLM-Antworten zu erhalten, müssen alle Dependencies korrekt installiert werden."
    else:
        response_text = f"[Verbessert] Erweiterte Antwort auf: '{user_message}'\n\nDies ist die verbesserte Version mit erweitertem Kontext-Fenster. Um die echten LLM-Antworten zu erhalten, müssen alle Dependencies korrekt installiert werden."
    
    # Wenn Streaming angefordert wird
    if request.stream:
        async def generate_stream():
            completion_id = f"chatcmpl-test-{abs(hash(response_text))}"
            created = int(time.time())
            
            # Sende Response in Chunks (simuliere Token-by-Token)
            words = response_text.split()
            for i, word in enumerate(words):
                chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": request.model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "content": word + " " if i < len(words) - 1 else word
                            },
                            "finish_reason": None
                        }
                    ]
                }
                yield f"data: {json.dumps(chunk)}\n\n"
                await asyncio.sleep(0.01)  # Kleine Verzögerung für Realismus
            
            # Sende finalen Chunk mit finish_reason
            final_chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": request.model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }
                ]
            }
            yield f"data: {json.dumps(final_chunk)}\n\n"
            yield "data: [DONE]\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    
    # Nicht-Streaming Response (wie vorher)
    response_data = {
        "id": f"chatcmpl-test-{abs(hash(response_text))}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
                },
                "finish_reason": "stop",
                "logprobs": None
            }
        ],
        "usage": {
            "prompt_tokens": len(user_message.split()),
            "completion_tokens": len(response_text.split()),
            "total_tokens": len(user_message.split()) + len(response_text.split())
        },
        "system_fingerprint": None
    }
    
    return response_data


@app.get("/health")
def health():
    return {"status": "healthy", "mode": "test"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
