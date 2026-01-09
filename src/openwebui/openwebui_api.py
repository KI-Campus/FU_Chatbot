"""
OpenWebUI-kompatible API für Chatbot Arena Benchmarking.

Dieser Service stellt zwei Versionen des KI-Campus Chatbots bereit:
- Version A (Original): Die aktuelle Produktionsversion
- Version B (Verbessert): Eine optimierte Version mit Verbesserungen

Beide Versionen können in OpenWebUI's Arena-Modus gegeneinander getestet werden.
"""

from typing import AsyncGenerator, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langfuse.decorators import observe
from llama_index.core.llms import ChatMessage, MessageRole
from pydantic import BaseModel, Field

from src.llm.assistant import KICampusAssistant
from src.llm.LLMs import Models
from src.openwebui.assistant_improved import KICampusAssistantImproved

app = FastAPI(
    title="KI-Campus Chatbot Arena API",
    description="OpenWebUI-kompatible API für Chatbot Benchmarking",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In Produktion einschränken
    allow_methods=["*"],
    allow_headers=["*"],
)


# OpenWebUI-kompatible Request/Response Modelle
class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = Field(description="Model identifier: 'kicampus-original' or 'kicampus-improved'")
    messages: list[Message]
    stream: bool = Field(default=False)
    temperature: float = Field(default=0.7)
    max_tokens: int | None = Field(default=None)


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


# Globale Assistenten-Instanzen
assistant_original = KICampusAssistant()
assistant_improved = KICampusAssistantImproved()


def convert_messages_to_chat_history(messages: list[Message]) -> tuple[list[ChatMessage], str]:
    """
    Konvertiert OpenWebUI Messages in LlamaIndex ChatMessages.
    
    Returns:
        Tuple von (chat_history ohne letzte Nachricht, letzte User-Nachricht)
    """
    chat_history = []
    
    for msg in messages[:-1]:  # Alle außer der letzten
        role = MessageRole.USER if msg.role == "user" else MessageRole.ASSISTANT
        chat_history.append(ChatMessage(content=msg.content, role=role))
    
    # Letzte Nachricht sollte vom User sein
    if messages[-1].role != "user":
        raise ValueError("Last message must be from user")
    
    return chat_history, messages[-1].content


@app.get("/")
def root():
    """Health check endpoint."""
    return {
        "status": "online",
        "service": "KI-Campus Chatbot Arena",
        "available_models": ["kicampus-original", "kicampus-improved"],
    }


@app.get("/v1/models")
def list_models() -> ModelsResponse:
    """
    OpenWebUI-kompatibler Endpoint zum Auflisten verfügbarer Modelle.
    """
    return ModelsResponse(
        data=[
            ModelInfo(
                id="kicampus-original",
                created=1700000000,
                owned_by="ki-campus",
            ),
            ModelInfo(
                id="kicampus-improved",
                created=1700000000,
                owned_by="ki-campus",
            ),
        ]
    )


@app.post("/v1/chat/completions")
@observe()
async def chat_completions(request: ChatCompletionRequest) -> ChatCompletionResponse | StreamingResponse:
    """
    OpenWebUI-kompatibler Chat Completion Endpoint.
    
    Unterstützt zwei Modelle:
    - kicampus-original: Die aktuelle Produktionsversion
    - kicampus-improved: Eine verbesserte Version mit Optimierungen
    """
    try:
        # Konvertiere Messages
        chat_history, user_query = convert_messages_to_chat_history(request.messages)
        
        # Wähle den richtigen Assistenten basierend auf dem Modell
        if request.model == "kicampus-original":
            assistant = assistant_original
            llm_model = Models.GPT4
        elif request.model == "kicampus-improved":
            assistant = assistant_improved
            llm_model = Models.GPT4  # Kann später geändert werden
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown model: {request.model}. Available: kicampus-original, kicampus-improved",
            )
        
        # Generiere Antwort
        response = assistant.chat(
            query=user_query,
            model=llm_model,
            chat_history=chat_history,
        )
        
        # Streaming wird aktuell nicht unterstützt
        if request.stream:
            raise HTTPException(
                status_code=400,
                detail="Streaming is not yet supported",
            )
        
        # Rückgabe im OpenWebUI-kompatiblen Format
        return ChatCompletionResponse(
            id=f"chatcmpl-{hash(response.content)}",
            created=1700000000,
            model=request.model,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=Message(
                        role="assistant",
                        content=response.content,
                    ),
                    finish_reason="stop",
                )
            ],
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    """Health check für Kubernetes/Docker."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
