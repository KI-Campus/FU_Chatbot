"""Base classes and registry for H5P content type handlers."""
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Type

logger = logging.getLogger(__name__)


class H5PContentBase(ABC):
    """Abstract base class for all H5P content types."""
    
    @classmethod
    @abstractmethod
    def from_h5p_params(cls, library: str, params: dict):
        """Extract content from H5P params dict."""
        pass
    
    @classmethod
    @abstractmethod
    def from_h5p_package(cls, module, content: dict, h5p_zip_path: str, **kwargs) -> Optional[str]:
        """
        Handler for standalone H5P content.
        Returns error message or None on success.
        """
        pass
    
    @abstractmethod
    def to_text(self) -> str:
        """Convert content to text representation."""
        pass


class H5PLeaf(H5PContentBase):
    """Base class for leaf content types (cannot contain other H5P content)."""
    pass


class H5PContainer(H5PContentBase):
    """Base class for container content types (can contain other H5P content)."""
    
    @classmethod
    def extract_child_content(cls, library: str, params: dict) -> Optional[H5PContentBase]:
        """
        Generic method to extract child content using the registry.
        Uses substring matching to find appropriate handler.
        """
        handler_class = get_handler_for_library(library)
        if handler_class:
            return handler_class.from_h5p_params(library, params)
        else:
            logger.debug(f"⚠️  H5P-Typ nicht unterstützt: {library}")
            return None


# Global registry: Maps H5P library name patterns to handler classes
H5P_TYPE_REGISTRY: Dict[str, Type[H5PContentBase]] = {}


def register_h5p_type(library_pattern: str, handler_class: Type[H5PContentBase]) -> None:
    """Register an H5P type handler in the global registry."""
    H5P_TYPE_REGISTRY[library_pattern] = handler_class


def get_handler_for_library(library: str) -> Optional[Type[H5PContentBase]]:
    """
    Find handler for library string using substring matching.
    Returns first matching handler or None.
    """
    for pattern, handler_class in H5P_TYPE_REGISTRY.items():
        if pattern in library:
            return handler_class
    return None


def initialize_registry():
    """Populate the H5P type registry with all known handlers."""
    from src.loaders.models.h5pactivities.h5p_basics import Text, H5PVideo
    from src.loaders.models.h5pactivities.h5p_quiz_questions import QuizQuestion, TrueFalseQuestion
    from src.loaders.models.h5pactivities.h5p_blanks import FillInBlanksQuestion
    from src.loaders.models.h5pactivities.h5p_drag_drop import DragDropQuestion, DragDropText, ImageHotspotQuestion
    from src.loaders.models.h5pactivities.h5p_dialogcards import H5PDialogcards
    from src.loaders.models.h5pactivities.h5p_flashcards import H5PFlashcards
    from src.loaders.models.h5pactivities.h5p_timeline import H5PTimeline
    from src.loaders.models.h5pactivities.h5p_summary import Summary
    from src.loaders.models.h5pactivities.h5p_question_set import QuestionSet
    from src.loaders.models.h5pactivities.h5p_interactive_video import InteractiveVideo
    from src.loaders.models.h5pactivities.h5p_wrappers import Column, Accordion, Gamemap, CoursePresentation
    from src.loaders.models.h5pactivities.h5p_crossword import Crossword
    
    # Register leaf types
    register_h5p_type("H5P.Text", Text)
    register_h5p_type("H5P.AdvancedText", Text)
    register_h5p_type("H5P.Video", H5PVideo)
    register_h5p_type("H5P.MultiChoice", QuizQuestion)
    register_h5p_type("H5P.SingleChoiceSet", QuizQuestion)
    register_h5p_type("H5P.TrueFalse", TrueFalseQuestion)
    register_h5p_type("H5P.Blanks", FillInBlanksQuestion)
    register_h5p_type("H5P.DragQuestion", DragDropQuestion)
    register_h5p_type("H5P.DragText", DragDropText)
    register_h5p_type("H5P.ImageHotspot", ImageHotspotQuestion)
    register_h5p_type("H5P.Dialogcards", H5PDialogcards)
    register_h5p_type("H5P.Flashcards", H5PFlashcards)
    register_h5p_type("H5P.Timeline", H5PTimeline)
    register_h5p_type("H5P.Summary", Summary)
    register_h5p_type("H5P.Crossword", Crossword)
    
    # Register container types
    register_h5p_type("H5P.QuestionSet", QuestionSet)
    register_h5p_type("H5P.InteractiveVideo", InteractiveVideo)
    register_h5p_type("H5P.Column", Column)
    register_h5p_type("H5P.Accordion", Accordion)
    register_h5p_type("H5P.Gamemap", Gamemap)
    register_h5p_type("H5P.GameMap", Gamemap)  # Alternative spelling
    register_h5p_type("H5P.CoursePresentation", CoursePresentation)


# Initialize registry on module import
initialize_registry()
