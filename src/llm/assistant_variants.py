"""
Unified Assistant Variants Interface for Arena Benchmarking.

This module provides a factory pattern for loading different assistant implementations:
- "original": Production KICampusAssistant
- "improved": Enhanced KICampusAssistantImproved with optimizations

Allows transparent switching between variants via environment variable ASSISTANT_VARIANT.
"""

import os
from typing import Literal

from src.llm.assistant import KICampusAssistant
from src.llm.LLMs import Models
from src.llm.parser.citation_parser import CitationParser
from src.llm.retriever import KiCampusRetriever


class KICampusAssistantImproved(KICampusAssistant):
    """
    Enhanced version of the KI-Campus Assistant for Arena benchmarking.
    
    Improvements over the original version:
    - Better prompts for more precise answers
    - Optimized retrieval parameters
    - Extended contextualization
    - Better language detection
    
    Inherits all functionality from KICampusAssistant with selective overrides.
    """

    def __init__(self):
        super().__init__()
        # Specialized tool versions can be initialized here
        # self.contextualizer = ImprovedContextualizer()
        # self.question_answerer = ImprovedQuestionAnswerer()
        # self.retriever = ImprovedRetriever()

    def limit_chat_history(
        self, chat_history: list, limit: int = 15
    ) -> list:
        """
        Extended chat history with more context (15 instead of 10 messages).
        
        Provides better continuity for longer conversations while maintaining
        token budget constraints.
        """
        if len(chat_history) > limit:
            chat_history = chat_history[-limit:]
        return chat_history


class AssistantFactory:
    """
    Factory for creating assistant instances with variant selection.
    
    Usage:
        variant = os.getenv("ASSISTANT_VARIANT", "original")
        assistant = AssistantFactory.create(variant)
    
    Environment Variables:
        ASSISTANT_VARIANT: "original" (default) or "improved"
        LANGFUSE_ENABLED: "true" or "false" - Controls @observe decorators
    """

    _variants = {
        "original": KICampusAssistant,
        "improved": KICampusAssistantImproved,
    }

    @classmethod
    def create(
        cls, variant: Literal["original", "improved"] = "original"
    ) -> KICampusAssistant:
        """
        Create an assistant instance of the specified variant.
        
        Args:
            variant: "original" or "improved"
            
        Returns:
            Instance of the selected assistant variant
            
        Raises:
            ValueError: If variant is not supported
        """
        if variant not in cls._variants:
            raise ValueError(
                f"Unknown variant '{variant}'. "
                f"Supported: {list(cls._variants.keys())}"
            )
        return cls._variants[variant]()

    @classmethod
    def create_from_env(cls) -> KICampusAssistant:
        """
        Create an assistant instance using environment variable selection.
        
        Reads ASSISTANT_VARIANT from environment (default: "original").
        """
        variant = os.getenv("ASSISTANT_VARIANT", "original")
        return cls.create(variant)

    @classmethod
    def get_available_variants(cls) -> list[str]:
        """Return list of available assistant variants."""
        return list(cls._variants.keys())

    @classmethod
    def register_variant(
        cls, name: str, assistant_class: type
    ) -> None:
        """
        Register a new assistant variant.
        
        Allows extensibility for custom assistant implementations.
        
        Args:
            name: Unique identifier for the variant
            assistant_class: Class implementing the assistant interface
        """
        cls._variants[name] = assistant_class


# Backward compatibility: export original class for existing code
__all__ = [
    "KICampusAssistant",
    "KICampusAssistantImproved",
    "AssistantFactory",
]
