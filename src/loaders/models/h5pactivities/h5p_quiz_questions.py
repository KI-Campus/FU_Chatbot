from dataclasses import dataclass, field
from typing import Optional
from src.loaders.models.hp5activities import strip_html


@dataclass
class QuizQuestion:
    """Quiz-Frage (Multiple/Single Choice) im Interactive Video."""
    type: str  # "H5P.MultiChoice" oder "H5P.SingleChoiceSet"
    question: str
    correct_answers: list[str]
    incorrect_answers: list[str] = field(default_factory=list)
    
    @classmethod
    def from_h5p_package(cls, module, content: dict, h5p_zip_path: str, **kwargs) -> Optional[str]:
        """
        Handler für standalone H5P.MultiChoice / H5P.SingleChoiceSet.
        Befüllt module.interactive_video mit einer Quiz-Frage.
        
        Args:
            module: Module-Objekt zum Befüllen
            content: Geladenes content.json dict
            h5p_zip_path: Pfad zum H5P ZIP-File (nicht verwendet)
            **kwargs: Zusätzliche Services (nicht verwendet)
            
        Returns:
            Optional[str]: Fehlermeldung oder None
        """
        library = content.get("library", "")
        params = content.get("params", {})
        
        quiz = cls.from_h5p_params(library, params)
        
        if quiz:
            # Speichere als dict (Dependency Inversion)
            module.interactive_video = {
                "video_url": "",
                "vimeo_id": None,
                "interactions": [quiz.to_text()]
            }
            return None
        
        return "Konnte Quiz-Frage nicht extrahieren"
    
    @classmethod
    def from_h5p_params(cls, library: str, params: dict) -> Optional['QuizQuestion']:
        """Extrahiert QuizQuestion aus H5P params."""
        # MultiChoice
        if "H5P.MultiChoice" in library:
            question_text = params.get("question", "").strip()
            
            correct = []
            incorrect = []
            for answer in params.get("answers", []):
                text = answer.get("text", "").strip()
                if text:
                    if answer.get("correct"):
                        correct.append(text)
                    else:
                        incorrect.append(text)
            
            if question_text and correct:
                return cls(
                    type=library,
                    question=question_text,
                    correct_answers=correct,
                    incorrect_answers=incorrect
                )
        
        # SingleChoiceSet
        elif "H5P.SingleChoiceSet" in library:
            choices = params.get("choices", [])
            results = []
            
            for choice in choices:
                question_text = choice.get("question", "").strip()
                answers = choice.get("answers", [])
                
                if question_text and answers:
                    # First answer is always correct in SingleChoiceSet
                    correct = [answers[0].strip()] if answers else []
                    incorrect = [a.strip() for a in answers[1:] if a.strip()]
                    
                    if correct:
                        results.append(cls(
                            type=library,
                            question=question_text,
                            correct_answers=correct,
                            incorrect_answers=incorrect
                        ))
            
            # Return first question or None
            return results[0] if results else None
        
        return None
    
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
    
    @classmethod
    def from_h5p_package(cls, module, content: dict, h5p_zip_path: str, **kwargs) -> Optional[str]:
        """
        Handler für standalone H5P.TrueFalse.
        Befüllt module.interactive_video mit einer True/False-Frage.
        """
        library = content.get("library", "")
        params = content.get("params", {})
        
        question = cls.from_h5p_params(library, params)
        
        if question:
            # Speichere als dict (Dependency Inversion)
            module.interactive_video = {
                "video_url": "",
                "vimeo_id": None,
                "interactions": [question.to_text()]
            }
            return None
        
        return "Konnte True/False-Frage nicht extrahieren"
    
    @classmethod
    def from_h5p_params(cls, library: str, params: dict) -> Optional['TrueFalseQuestion']:
        """Extrahiert TrueFalseQuestion aus H5P params."""
        question_text = params.get("question", "").strip()
        correct_str = params.get("correct", "").lower()
        
        if question_text and correct_str in ["true", "false"]:
            correct_answer = (correct_str == "true")
            return cls(
                type=library,
                question=question_text,
                correct_answer=correct_answer
            )
        
        return None
    
    def to_text(self) -> str:
        question_clean = strip_html(self.question)
        answer = "Wahr" if self.correct_answer else "Falsch"
        return f"[Wahr/Falsch] {question_clean}\nKorrekte Antwort: {answer}"
