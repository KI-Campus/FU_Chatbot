from dataclasses import dataclass
from typing import Optional
from src.loaders.models.hp5activities import strip_html


@dataclass
class FillInBlanksQuestion:
    """Lückentext-Frage im Interactive Video."""
    type: str  # "H5P.Blanks"
    question: str
    text_with_blanks: str
    blank_indicator: str = "**"
    
    @classmethod
    def from_h5p_package(cls, module, content: dict, h5p_zip_path: str, **kwargs) -> Optional[str]:
        """
        Handler für standalone H5P.Blanks.
        Befüllt module.interactive_video mit einem Lückentext.
        """
        library = content.get("library", "")
        params = content.get("params", {})
        
        blanks = cls.from_h5p_params(library, params)
        
        if blanks:
            # Speichere als dict (Dependency Inversion)
            module.interactive_video = {
                "video_url": "",
                "vimeo_id": None,
                "interactions": [blanks.to_text()]
            }
            return None
        
        return "Konnte Lückentext nicht extrahieren"
    
    @classmethod
    def from_h5p_params(cls, library: str, params: dict) -> Optional['FillInBlanksQuestion']:
        """Extrahiert FillInBlanksQuestion aus H5P params."""
        intro_text = params.get("text", "").strip()
        questions = params.get("questions", [])
        
        if questions:
            # Erstes Element ist der eigentliche Lückentext
            text_with_blanks = questions[0].strip() if questions else ""
            
            if intro_text or text_with_blanks:
                question_text = intro_text if intro_text else "Lückentext"
                return cls(
                    type=library,
                    question=question_text,
                    text_with_blanks=text_with_blanks
                )
        
        return None
    
    def to_text(self) -> str:
        question_clean = strip_html(self.question)
        text_clean = strip_html(self.text_with_blanks)
        return f"[Lückentext] {question_clean}\n{text_clean}"