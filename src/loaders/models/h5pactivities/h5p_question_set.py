import logging
from dataclasses import dataclass, field
from typing import Union, Optional
from src.loaders.models.hp5activities import extract_library_from_h5p
from src.loaders.models.h5pactivities.h5p_base import H5PContainer
from src.loaders.models.h5pactivities.h5p_quiz_questions import QuizQuestion, TrueFalseQuestion
from src.loaders.models.h5pactivities.h5p_blanks import FillInBlanksQuestion
from src.loaders.models.h5pactivities.h5p_drag_drop import DragDropQuestion, DragDropText

logger = logging.getLogger(__name__)


# Union-Type für alle unterstützten Fragetypen
QuestionType = Union[
    QuizQuestion,
    TrueFalseQuestion,
    FillInBlanksQuestion,
    DragDropQuestion,
    DragDropText
]


@dataclass
class QuestionSet(H5PContainer):
    """H5P.QuestionSet - Container für mehrere Quiz-Fragen verschiedener Typen."""
    type: str = "H5P.QuestionSet"
    questions: list[QuestionType] = field(default_factory=list)
    intro_text: str = ""
    
    @classmethod
    def from_h5p_package(cls, module, content: dict, h5p_zip_path: str, **kwargs) -> Optional[str]:
        """
        Handler für standalone H5P.QuestionSet.
        Befüllt module.interactive_video mit allen Fragen aus dem QuestionSet.
        
        Args:
            module: Module-Objekt zum Befüllen
            content: Geladenes content.json dict
            h5p_zip_path: Pfad zum H5P ZIP-File (nicht verwendet)
            **kwargs: Zusätzliche Services (nicht verwendet)
            
        Returns:
            Optional[str]: Fehlermeldung oder None
        """
        # Bei standalone QuestionSet ist content direkt die Struktur mit questions
        # NICHT unter params wie bei anderen H5P-Typen
        library = extract_library_from_h5p(h5p_zip_path) or "H5P.QuestionSet"
        
        question_set = cls.from_h5p_params(library, content)
        
        if question_set and question_set.questions:
            # Speichere als dict (Dependency Inversion)
            # Alle Fragen werden als separate Texte gespeichert
            module.interactive_video = {
                "video_url": "",
                "vimeo_id": None,
                "interactions": [q.to_text() for q in question_set.questions]
            }
            return None
        
        return "Konnte QuestionSet nicht extrahieren oder keine Fragen gefunden"
    
    @classmethod
    def from_h5p_params(cls, library: str, params: dict) -> Optional['QuestionSet']:
        """
        Extrahiert QuestionSet aus H5P params.
        
        Iteriert durch alle Fragen und verwendet die bestehenden Handler
        für jeden Fragetyp (QuizQuestion, TrueFalseQuestion, etc.).
        """
        # Optional: Intro-Text extrahieren
        intro_page = params.get("introPage", {})
        intro_text = intro_page.get("introduction", "").strip()
        
        # Alle Fragen extrahieren
        extracted_questions = []
        
        for question_data in params.get("questions", []):
            q_library = question_data.get("library", "")
            q_params = question_data.get("params", {})
            
            if not q_library or not q_params:
                continue
            
            # Verwende bestehende Handler für jeden Fragetyp
            extracted = QuestionSet.extract_child_content(q_library, q_params)
            
            if extracted:
                extracted_questions.append(extracted)
        
        if extracted_questions:
            return cls(
                type=library,
                questions=extracted_questions,
                intro_text=intro_text
            )
        
        return None
    
    def to_text(self) -> str:
        """Formatiert QuestionSet als Text mit allen Fragen."""
        lines = []
        
        if self.intro_text:
            lines.append(f"[QuestionSet] {self.intro_text}")
        else:
            lines.append(f"[QuestionSet] {len(self.questions)} Fragen")
        
        lines.append("")
        
        for i, question in enumerate(self.questions, start=1):
            lines.append(f"--- Frage {i} ---")
            lines.append(question.to_text())
            lines.append("")
        
        return "\n".join(lines)
