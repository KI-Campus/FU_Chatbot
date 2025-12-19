import logging
from dataclasses import dataclass, field
from typing import Union, Optional, Any
from src.loaders.models.h5pactivities.h5p_quiz_questions import QuizQuestion, TrueFalseQuestion
from src.loaders.models.h5pactivities.h5p_blanks import FillInBlanksQuestion
from src.loaders.models.h5pactivities.h5p_drag_drop import DragDropQuestion, DragDropText
from src.loaders.models.hp5activities import strip_html

logger = logging.getLogger(__name__)


# Union-Type für alle unterstützten Inhaltstypen
ColumnContent = Union[
    QuizQuestion,
    TrueFalseQuestion,
    FillInBlanksQuestion,
    DragDropQuestion,
    DragDropText,
    Any  # Fallback für nicht unterstützte Typen (werden als Text rendert)
]


@dataclass
class Column:
    """
    H5P.Column - Extrem oberflächlicher Wrapper für mehrere H5P-Inhalte.
    
    Column ordnet verschiedene H5P-Inhalte untereinander an.
    Es können beliebige H5P-Typen in beliebiger Reihenfolge vorkommen.
    """
    type: str = "H5P.Column"
    contents: list[ColumnContent] = field(default_factory=list)
    
    @classmethod
    def from_h5p_package(cls, module, content: dict, h5p_zip_path: str, **kwargs) -> Optional[str]:
        """
        Handler für standalone H5P.Column.
        Befüllt module.interactive_video mit allen Inhalten aus der Column.
        
        Args:
            module: Module-Objekt zum Befüllen
            content: Geladenes content.json dict
            h5p_zip_path: Pfad zum H5P ZIP-File (nicht verwendet)
            **kwargs: Zusätzliche Services (nicht verwendet)
            
        Returns:
            Optional[str]: Fehlermeldung oder None
        """
        library = "H5P.Column"  # Für standalone ist library nicht in content
        
        column = cls.from_h5p_params(library, content)
        
        if column and column.contents:
            # Speichere als dict (Dependency Inversion)
            # Alle Inhalte werden als separate Texte gespeichert
            module.interactive_video = {
                "video_url": "",
                "vimeo_id": None,
                "interactions": [c.to_text() if hasattr(c, 'to_text') else str(c) for c in column.contents]
            }
            return None
        
        return "Konnte Column nicht extrahieren oder keine Inhalte gefunden"
    
    @classmethod
    def from_h5p_params(cls, library: str, params: dict) -> Optional['Column']:
        """
        Extrahiert Column aus H5P params.
        
        Iteriert durch alle content-Items und versucht, den passenden Handler
        für jeden Inhaltstyp zu finden.
        """
        extracted_contents = []
        
        for item in params.get("content", []):
            # Der eigentliche Inhalt ist nested in "content" Key
            content_data = item.get("content", {})
            
            if not content_data:
                continue
            
            content_library = content_data.get("library", "")
            content_params = content_data.get("params", {})
            
            if not content_library or not content_params:
                continue
            
            # Verwende bestehende Handler für jeden unterstützten Fragetyp
            extracted = None
            
            # MultiChoice / SingleChoiceSet
            if "H5P.MultiChoice" in content_library or "H5P.SingleChoiceSet" in content_library:
                extracted = QuizQuestion.from_h5p_params(content_library, content_params)
            
            # TrueFalse
            elif "H5P.TrueFalse" in content_library:
                extracted = TrueFalseQuestion.from_h5p_params(content_library, content_params)
            
            # Blanks
            elif "H5P.Blanks" in content_library:
                extracted = FillInBlanksQuestion.from_h5p_params(content_library, content_params)
            
            # DragQuestion
            elif "H5P.DragQuestion" in content_library:
                extracted = DragDropQuestion.from_h5p_params(content_library, content_params)
            
            # DragText
            elif "H5P.DragText" in content_library:
                extracted = DragDropText.from_h5p_params(content_library, content_params)
            
            # AdvancedText / Text
            elif "H5P.AdvancedText" in content_library or "H5P.Text" in content_library:
                # Einfachen Text extrahieren
                text_content = content_params.get("text", "").strip()
                if text_content:
                    extracted = SimpleTextContent(
                        type=content_library,
                        text=text_content
                    )
            
            # Fallback: Unsupported Typen
            else:
                # Logger-Warnung für nicht unterstützte Typen
                logger.debug(f"⚠️  H5P-Typ nicht unterstützt in Column: {content_library}")
                # Ignorieren, nicht in extracted_contents hinzufügen
                pass
            
            if extracted:
                extracted_contents.append(extracted)
        
        if extracted_contents:
            return cls(
                type=library,
                contents=extracted_contents
            )
        
        return None
    
    def to_text(self) -> str:
        """Formatiert Column als Text mit allen Inhalten."""
        lines = []
        lines.append(f"[Column] {len(self.contents)} Inhalte")
        lines.append("")
        
        for i, content in enumerate(self.contents, start=1):
            lines.append(f"--- Inhalt {i} ---")
            if hasattr(content, 'to_text'):
                lines.append(content.to_text())
            else:
                lines.append(str(content))
            lines.append("")
        
        return "\n".join(lines)


@dataclass
class SimpleTextContent:
    """Einfacher Text-Inhalt aus H5P.AdvancedText oder H5P.Text."""
    type: str
    text: str
    
    def to_text(self) -> str:
        text_clean = strip_html(self.text)
        return f"[Text] {text_clean}"
