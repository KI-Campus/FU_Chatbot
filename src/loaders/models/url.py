"""Datenmodell für Moodle URL Module.

Ein URL-Modul repräsentiert einen Link zu einer externen Ressource.
"""

from pydantic import BaseModel, HttpUrl


class UrlModule(BaseModel):
    """
    Repräsentiert ein URL-Modul aus Moodle.
    
    URL-Module können auf externe Websites oder Dateien verweisen.
    Wenn die URL auf eine verarbeitbare Datei (PDF, HTML, Audio, TXT) verweist,
    wird diese als Resource extrahiert. Andernfalls wird nur der Link gespeichert.
    
    Attributes:
        url_id: ID des URL-Moduls in Moodle (aus instance-Feld)
        module_id: ID des Course-Moduls
        external_url: Die tatsächliche externe URL
        display: Display-Modus (0=automatisch, 1=embed, 6=popup, etc.)
        intro: Einführungstext (HTML, wird zu Text konvertiert)
    """
    
    url_id: int
    module_id: int
    external_url: str
    display: int | None = None
    intro: str | None = None  # Als Text (nicht HTML)
    
    def __str__(self) -> str:
        """String-Repräsentation für Document-Generierung."""
        parts = []
        
        if self.intro:
            parts.append(self.intro)
        
        parts.append(f"Link zu: {self.external_url}")
        
        return "\n\n".join(parts)
