"""
OpenWebUI-kompatible API mit echter Azure OpenAI Integration - Ohne Key Vault Dependency.
Verwendet direkt .env Datei für Konfiguration.
"""

import asyncio
import json
import os
import time
from typing import AsyncGenerator, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from llama_index.core.llms import ChatMessage, MessageRole
from pydantic import BaseModel, Field

# Lade .env Datei
load_dotenv()

app = FastAPI(
    title="KI-Campus Chatbot Arena API",
    description="OpenWebUI-kompatible API mit Azure OpenAI Integration",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy-Loading der Assistenten (erst beim ersten Request)
_assistant_original = None
_assistant_improved = None


def get_assistant_original():
    global _assistant_original
    if _assistant_original is None:
        from src.llm.assistant import KICampusAssistant
        _assistant_original = KICampusAssistant()
    return _assistant_original


def get_assistant_improved():
    global _assistant_improved
    if _assistant_improved is None:
        from src.openwebui.assistant_improved import KICampusAssistantImproved
        _assistant_improved = KICampusAssistantImproved()
    return _assistant_improved


class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[Message]
    stream: bool = Field(default=False)
    temperature: float = Field(default=0.0)
    max_tokens: int = Field(default=400)


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
        "service": "KI-Campus Chatbot Arena",
        "available_models": ["kicampus-original", "kicampus-improved"],
        "llm_backend": "Azure OpenAI + GWDG",
        "azure_configured": bool(os.getenv("AZURE_OPENAI_API_KEY")),
    }


@app.get("/v1/models")
def list_models() -> ModelsResponse:
    return ModelsResponse(
        data=[
            ModelInfo(id="kicampus-original", created=1700000000, owned_by="ki-campus"),
            ModelInfo(id="kicampus-improved", created=1700000000, owned_by="ki-campus"),
        ]
    )


def convert_to_llama_messages(messages: list[Message]) -> list[ChatMessage]:
    """Konvertiert OpenAI-Format zu LlamaIndex ChatMessage Format."""
    llama_messages = []
    for msg in messages:
        if msg.role == "system":
            role = MessageRole.SYSTEM
        elif msg.role == "assistant":
            role = MessageRole.ASSISTANT
        else:
            role = MessageRole.USER
        llama_messages.append(ChatMessage(role=role, content=msg.content))
    return llama_messages


async def stream_llm_response(
    assistant,
    query: str,
    chat_history: list[ChatMessage],
    model,
    request_model: str,
) -> AsyncGenerator[str, None]:
    """
    Streamt die LLM-Response als Server-Sent Events (SSE).
    
    Da LlamaIndex standardmäßig keine Token-by-Token Streaming-API hat,
    simulieren wir Streaming durch Wort-basierte Chunks.
    """
    completion_id = f"chatcmpl-{abs(hash(query + str(time.time())))}"
    created = int(time.time())
    
    try:
        # Hole die vollständige Response vom LLM
        from src.llm.LLMs import Models
        
        response = await asyncio.to_thread(
            assistant.chat,
            query=query,
            model=Models.GPT4,
            chat_history=chat_history
        )
        
        response_text = response.content
        
        # Streame die Response wortweise
        words = response_text.split()
        for i, word in enumerate(words):
            chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": request_model,
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
            await asyncio.sleep(0.02)  # Kleine Verzögerung für visuelles Feedback
        
        # Sende finalen Chunk
        final_chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": request_model,
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
        
    except Exception as e:
        error_chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": request_model,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "content": f"\n\n[Fehler: {str(e)}]"
                    },
                    "finish_reason": "error"
                }
            ]
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"
        yield "data: [DONE]\n\n"


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """
    OpenAI-kompatible Chat-Completions mit echter LLM-Integration.
    Unterstützt sowohl Streaming als auch nicht-Streaming Responses.
    """
    
    if request.model not in ["kicampus-original", "kicampus-improved"]:
        raise HTTPException(status_code=400, detail=f"Unknown model: {request.model}")
    
    # Wähle den richtigen Assistenten
    if request.model == "kicampus-original":
        assistant = get_assistant_original()
    else:
        assistant = get_assistant_improved()
    
    # Extrahiere User-Query und Chat-History
    if not request.messages:
        raise HTTPException(status_code=400, detail="Messages list is empty")
    
    # Konvertiere zu LlamaIndex Format
    llama_messages = convert_to_llama_messages(request.messages)
    
    # Letzte User-Nachricht ist die Query
    user_messages = [msg for msg in llama_messages if msg.role == MessageRole.USER]
    if not user_messages:
        raise HTTPException(status_code=400, detail="No user message found")
    
    query = user_messages[-1].content
    
    # Chat-History ohne die letzte User-Nachricht
    chat_history = llama_messages[:-1]
    
    # Verwende GPT-4 als Basis-Modell
    from src.llm.LLMs import Models
    llm_model = Models.GPT4
    
    # Streaming-Response
    if request.stream:
        return StreamingResponse(
            stream_llm_response(
                assistant=assistant,
                query=query,
                chat_history=chat_history,
                model=llm_model,
                request_model=request.model
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    
    # Nicht-Streaming Response
    try:
        response = await asyncio.to_thread(
            assistant.chat,
            query=query,
            model=llm_model,
            chat_history=chat_history
        )
        
        response_text = response.content
        
        return {
            "id": f"chatcmpl-{abs(hash(response_text))}",
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
                "prompt_tokens": len(query.split()),
                "completion_tokens": len(response_text.split()),
                "total_tokens": len(query.split()) + len(response_text.split())
            },
            "system_fingerprint": None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Error: {str(e)}")


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "mode": "production",
        "azure_configured": bool(os.getenv("AZURE_OPENAI_API_KEY"))
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
