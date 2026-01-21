"""Utilities for request-scoped streaming.

We intentionally keep streaming control out of LangGraph state, because the
graph is checkpointed and expects JSON-serializable state.

Instead, we use a ContextVar that can be set by the FastAPI streaming endpoint.
Deep inside the LLM layer we can check whether a token callback is present.
"""

from __future__ import annotations

import contextvars
from typing import Callable, Optional


TokenCallback = Callable[[str], None]


# If set (per-request), the LLM layer will push generated token deltas into this callback.
token_callback_var: contextvars.ContextVar[Optional[TokenCallback]] = contextvars.ContextVar(
    "kic_token_callback",
    default=None,
)


# Gate streaming so only the *final* user-facing answer is streamed.
#
# Without this, internal LLM calls (routing/contextualization) will also stream
# their (often short) outputs like "simple_hop".
stream_phase_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "kic_stream_phase",
    default="none",  # none | final
)


class TokenCallbackContext:
    """Convenience context-manager to set/unset the token callback."""

    def __init__(self, callback: Optional[TokenCallback]):
        self._callback = callback
        self._token: Optional[contextvars.Token] = None

    def __enter__(self):
        self._token = token_callback_var.set(self._callback)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._token is not None:
            token_callback_var.reset(self._token)
        return False


class StreamPhaseContext:
    """Context manager to set the current streaming phase.

    Use this to enable streaming only around the final answer generation.
    """

    def __init__(self, phase: str):
        self._phase = phase
        self._token: Optional[contextvars.Token] = None

    def __enter__(self):
        self._token = stream_phase_var.set(self._phase)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._token is not None:
            stream_phase_var.reset(self._token)
        return False
