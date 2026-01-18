from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from langfuse import Langfuse
from langfuse.decorators import langfuse_context, observe
from llama_index.core.llms import ChatMessage, MessageRole
from pydantic import BaseModel, Field, field_validator, model_validator

from src.api.models.serializable_chat_message import SerializableChatMessage
from src.env import env
from src.llm.assistant import KICampusAssistant
from src.llm.objects.LLMs import Models
from src.vectordb.qdrant import VectorDBQdrant

# Singleton instances for performance - avoid recreating on every request
_vector_db = VectorDBQdrant()
_assistant = KICampusAssistant()

app = FastAPI()
# authentication with OAuth2
api_key_header = APIKeyHeader(name="Api-Key")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ki-campus.staging.piipe.de",
        "https://ki-campus.org",
        "https://moodle.ki-campus.org",
        "https://ki-campus.loom.de",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def api_key_auth(api_key: Annotated[str, Depends(api_key_header)]):
    ALLOWED_API_KEYS = env.REST_API_KEYS

    if api_key not in ALLOWED_API_KEYS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")


# APIs
@app.get("/health")
def health() -> str:
    """Health check endpoint. Returns 'OK' if the service is running."""
    return "OK"

# Definert aber nicht genutzt!
class RetrievalRequest(BaseModel):
    message: str = Field(
        description="The query to find the most fitting sources to.",
        examples=["Which course is teaching Ethics?"],
    )
    course_id: int | None = Field(
        default=None,
        description="The course identifier to restrict the search on.",
        examples=[79, 102, 91],
    )
    module_id: int | None = Field(
        default=None,
        description="The course module / topic / unit to restrict the search on. course_id is required when module_id is set.",
        examples=[1, 102, 33],
    )
    get_content_embeddings: bool = Field(
        default=False, description="If True, include the embeddings for the retrieved documents."
    )

    @model_validator(mode="after")
    def validate_module_id(self):
        if self.course_id and not self.module_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="module_id is required when course_id is set.",
            )
        return self


class ChatRequest(BaseModel):
    user_query: SerializableChatMessage = Field(
        description="The new user message. Should contain exactly one USER message.",
        examples=[
            SerializableChatMessage(content="I need help with my assignment", role=MessageRole.USER)
        ],
    )
    thread_id: str | None = Field(
        default=None,
        description="Thread ID for persistent conversations. If provided, chat history is loaded from backend checkpoint. If None, a new thread is created.",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    course_id: int | None = Field(
        default=None,
        description="The course identifier to restrict the search on.",
        examples=[79, 102, 91],
    )
    module_id: int | None = Field(
        default=None,
        description="The course module / topic / unit to restrict the search on. course_id is required when module_id is set.",
        examples=[1, 102, 33],
    )
    model: Models = Field(
        default=Models.GPT4,
        description="The LLM to use for the conversation.",
        examples=[Models.GPT4, Models.MISTRAL8],
    )

    def get_user_query(self) -> str:
        """Extract the query string from user_query SerializableChatMessage."""
        return self.user_query.content

    @model_validator(mode="after")
    def validate_module_id(self):
        if self.module_id and not self.course_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="module_id is required when course_id is set.",
            )
        if self.module_id is not None:
            if not _vector_db.check_if_module_exists(self.module_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"no module found with the given id: {self.module_id}.",
                )
        return self

    @model_validator(mode="after")
    def validate_course_id(self):
        if self.course_id is not None:
            if not _vector_db.check_if_course_exists(self.course_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"no course found with the given id: {self.course_id}.",
                )
        return self


class ChatResponse(BaseModel):
    message: str = Field(
        description="The assistant response to the user message.",
        examples=["I can help you with that. What is the assignment about?"],
    )
    response_id: str = Field(description="An ID for the response, that is needed for using the feedback endpoint.")
    thread_id: str = Field(
        description="The thread ID. Use this for subsequent requests to continue the conversation.",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )


@app.post("/api/chat", dependencies=[Depends(api_key_auth)])
@observe()
def chat(chat_request: ChatRequest) -> ChatResponse:
    """Returns the response to the user message in one response (no streaming)."""
    # Use singleton assistant for performance
    
    if chat_request.course_id is not None:
        # Chat with course content (with or without module filter)
        llm_response, thread_id = _assistant.chat_with_course(
            query=chat_request.get_user_query(),
            model=chat_request.model,
            course_id=chat_request.course_id,
            module_id=chat_request.module_id,  # Can be None
            thread_id=chat_request.thread_id,
        )
    else:
        # General chat (Drupal content)
        llm_response, thread_id = _assistant.chat(
            query=chat_request.get_user_query(), 
            model=chat_request.model,
            thread_id=chat_request.thread_id,
        )

    trace_id = langfuse_context.get_current_trace_id()
    if not trace_id:
        trace_id = "TRACING_UNAVAILABLE"
    
    # llm_response is SerializableChatMessage, extract content string
    chat_response = ChatResponse(
        message=llm_response.content,
        response_id=trace_id,
        thread_id=thread_id
    )
    return chat_response


class FeedbackRequest(BaseModel):
    response_id: str = Field(description="The ID of the response that the feedback belongs to.")
    feedback: str | None = Field(description="Feedback on the conversation.", default=None)
    score: int = Field(description="Score between 0 and 1, where 1 is good and 0 is bad.")

    @field_validator("score", mode="after")
    @classmethod
    def validate_score(cls, score: int) -> int:
        if not 0 <= score <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Score must be between 0 and 1.",
            )
        return score


@app.post("/api/feedback", dependencies=[Depends(api_key_auth)])
def track_feedback(feedback_request: FeedbackRequest) -> None:
    """Update feedback in langfuse logs."""
    Langfuse().score(
        trace_id=feedback_request.response_id,
        name="user-explicit-feedback",
        value=feedback_request.score,
        comment=feedback_request.feedback,
    )
