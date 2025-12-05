from pathlib import Path
from dataclasses import dataclass, field
from typing import Union, Optional
import re

from pydantic import BaseModel, HttpUrl, root_validator


def strip_html(text: str) -> str:
    """Entfernt HTML-Tags und dekodiert HTML-Entities."""
    if not text:
        return ""
    # Entferne HTML-Tags
    text = re.sub(r'<[^>]+>', '', text)
    # Ersetze HTML-Entities
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&amp;', '&')
    text = text.replace('&quot;', '"')
    # Entferne übermäßige Whitespaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


class H5PActivities(BaseModel):
    id: int
    coursemodule: int
    fileurl: HttpUrl
    filename: Path

    @root_validator(pre=True)
    def validate_fileurl(cls, values):
        values["fileurl"] = values["package"][0]["fileurl"]
        values["filename"] = values["package"][0]["filename"]
        return values


# === Interaktionen in Interactive Videos ===

@dataclass
class QuizQuestion:
    """Quiz-Frage (Multiple/Single Choice) im Interactive Video."""
    type: str  # "H5P.MultiChoice" oder "H5P.SingleChoiceSet"
    question: str
    correct_answers: list[str]
    incorrect_answers: list[str] = field(default_factory=list)
    
    def to_text(self) -> str:
        question_clean = strip_html(self.question)
        correct_clean = [strip_html(a) for a in self.correct_answers]
        incorrect_clean = [strip_html(a) for a in self.incorrect_answers]
        return f"[Quiz] {question_clean}\nKorrekte Antwort(en): {', '.join(correct_clean)}\nInkorrekte Antwort(en): {', '.join(incorrect_clean)}"


@dataclass
class TrueFalseQuestion:
    """Wahr/Falsch-Frage im Interactive Video."""
    type: str  # "H5P.TrueFalse"
    question: str
    correct_answer: bool
    
    def to_text(self) -> str:
        question_clean = strip_html(self.question)
        answer = "Wahr" if self.correct_answer else "Falsch"
        return f"[Wahr/Falsch] {question_clean}\nKorrekte Antwort: {answer}"


@dataclass
class FillInBlanksQuestion:
    """Lückentext-Frage im Interactive Video."""
    type: str  # "H5P.Blanks"
    question: str
    text_with_blanks: str
    blank_indicator: str = "**"
    
    def to_text(self) -> str:
        question_clean = strip_html(self.question)
        text_clean = strip_html(self.text_with_blanks)
        return f"[Lückentext] {question_clean}\n{text_clean}"


@dataclass
class DragDropQuestion:
    """Drag & Drop-Frage im Interactive Video."""
    type: str  # "H5P.DragQuestion"
    question: str
    categories: list[str]  # Dropzones/Kategorien
    draggable_items: list[str]  # Elemente zum Ziehen
    correct_mappings: dict[str, list[str]] = field(default_factory=dict)  # Kategorie -> Liste von Elementen
    
    def to_text(self) -> str:
        question_clean = strip_html(self.question)
        categories_clean = [strip_html(c) for c in self.categories]
        items_clean = [strip_html(i) for i in self.draggable_items]
        
        result = (
            f"[Drag & Drop] {question_clean}\n"
            f"Kategorien: {', '.join(categories_clean)}\n"
            f"Elemente: {', '.join(items_clean)}\n\n"
            f"Korrekte Zuordnung:\n"
        )
        
        for category, items in self.correct_mappings.items():
            category_clean = strip_html(category)
            items_clean_list = [strip_html(item) for item in items]
            result += f"  {category_clean}: {', '.join(items_clean_list)}\n"
        
        return result


@dataclass
class TextBanner:
    """Text-Einblendung im Interactive Video."""
    type: str  # z.B. "H5P.Text"
    text: str
    
    def to_text(self) -> str:
        text_clean = strip_html(self.text)
        return f"[Info] {text_clean}"


# Union-Type für alle Interaktionstypen
VideoInteraction = Union[
    QuizQuestion, 
    TrueFalseQuestion, 
    FillInBlanksQuestion, 
    DragDropQuestion, 
    TextBanner
]


@dataclass
class InteractiveVideo:
    """Parsed H5P Interactive Video Content."""
    video_url: str
    vimeo_id: Optional[str] = None
    interactions: list[VideoInteraction] = field(default_factory=list)
    
    def get_quiz_questions(self) -> list[VideoInteraction]:
        """Gibt alle Interaktionen zurück (Quiz, Lückentexte, etc.)."""
        return self.interactions
