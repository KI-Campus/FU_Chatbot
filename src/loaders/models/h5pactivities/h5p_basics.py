from dataclasses import dataclass
from typing import Optional
from src.loaders.models.hp5activities import strip_html


@dataclass
class Text:
    """Text-Einblendung im Interactive Video."""
    type: str  # z.B. "H5P.Text"
    text: str
    
    @classmethod
    def from_h5p_package(cls, module, content: dict, h5p_zip_path: str, **kwargs) -> Optional[str]:
        """
        Handler für standalone H5P.Text.
        Befüllt module.interactive_video mit einem Text-Element als dict.
        """
        library = content.get("library", "")
        params = content.get("params", {})
        
        text = cls.from_h5p_params(library, params)
        
        if text:
            # Speichere als dict (Dependency Inversion)
            module.interactive_video = {
                "video_url": "",
                "vimeo_id": None,
                "interactions": [text.to_text()]
            }
            return None
        
        return "Konnte Text nicht extrahieren"
    
    @classmethod
    def from_h5p_params(cls, library: str, params: dict) -> Optional['Text']:
        """Extrahiert Text aus H5P params."""
        text = params.get("text", "").strip()
        if text:
            return cls(
                type=library,
                text=text
            )
        return None
    
    def to_text(self) -> str:
        text_clean = strip_html(self.text)
        return f"[Info] {text_clean}"