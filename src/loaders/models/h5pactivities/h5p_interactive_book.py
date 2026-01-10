"""H5P Interactive Book handler - Container for chapters with various H5P content."""
import logging
from dataclasses import dataclass, field
from typing import Optional, Any

from src.loaders.models.hp5activities import extract_library_from_h5p, strip_html
from src.loaders.models.h5pactivities.h5p_base import H5PContainer

logger = logging.getLogger(__name__)


@dataclass
class BookChapter:
    """Ein Kapitel innerhalb eines Interactive Books."""
    title: str
    contents: list[Any] = field(default_factory=list)
    
    def to_text(self) -> str:
        """Formatiert das Kapitel als Text mit Titel und allen Inhalten."""
        lines = []
        
        for content in self.contents:
            if hasattr(content, 'to_text'):
                text_output = content.to_text()
            else:
                text_output = str(content)
            if text_output and text_output.strip():
                lines.append(text_output)
        
        return "\n".join(lines)


@dataclass
class InteractiveBook(H5PContainer):
    """
    H5P.InteractiveBook - Container für mehrere Kapitel mit verschiedenen H5P-Inhalten.
    
    Ein Interactive Book organisiert Inhalte in Kapiteln, wobei jedes Kapitel
    beliebige H5P-Inhaltstypen enthalten kann (Text, Videos, Quizze, etc.).
    """
    type: str = "H5P.InteractiveBook"
    cover_title: str = ""
    cover_description: str = ""
    chapters: list[BookChapter] = field(default_factory=list)
    
    @classmethod
    def from_h5p_package(cls, module, content: dict, h5p_zip_path: str, **kwargs) -> Optional[str]:
        """
        Handler für standalone H5P.InteractiveBook.
        Extrahiert alle Kapitel und deren Inhalte und befüllt module.interactive_video.
        
        Args:
            module: Module-Objekt zum Befüllen
            content: Geladenes content.json dict
            h5p_zip_path: Pfad zum H5P ZIP-File
            **kwargs: Zusätzliche Services (vimeo_service, video_service - nicht verwendet)
            
        Returns:
            Optional[str]: Fehlermeldung oder None
        """
        library = extract_library_from_h5p(h5p_zip_path) or "H5P.InteractiveBook"
        
        book = cls.from_h5p_params(library, content)
        
        if book and book.chapters:
            # Speichere als dict (Dependency Inversion)
            # Jedes Kapitel wird als separater Text gespeichert
            module.interactive_video = {
                "video_url": "",
                "vimeo_id": None,
                "interactions": [book.to_text()],
            }
            return None
        
        return "Konnte Interactive Book nicht extrahieren oder keine Kapitel gefunden"
    
    @classmethod
    def from_h5p_params(cls, library: str, params: dict) -> Optional['InteractiveBook']:
        """
        Extrahiert InteractiveBook aus H5P params.
        
        Iteriert durch alle Kapitel und verwendet die bestehenden Handler
        für jeden Inhaltstyp via Registry.
        """
        # Cover-Informationen extrahieren
        cover_title = ""
        cover_description = ""
        
        if params.get("showCoverPage"):
            book_cover = params.get("bookCover", {})
            cover_title = strip_html(book_cover.get("coverTitle", "")).strip()
            cover_description = strip_html(book_cover.get("coverDescription", "")).strip()
        
        # Kapitel extrahieren
        extracted_chapters = []
        
        for chapter_data in params.get("chapters", []):
            # Titel kann entweder direkt oder in metadata sein
            chapter_title = chapter_data.get("title", "")
            if not chapter_title:
                chapter_title = chapter_data.get("metadata", {}).get("title", "")
            chapter_title = strip_html(chapter_title).strip()
            
            chapter_contents = []
            
            # Inhalte können direkt unter "content" oder unter "params.content" liegen
            content_items = chapter_data.get("content", [])
            if not content_items:
                content_items = chapter_data.get("params", {}).get("content", [])
            
            # Inhalte des Kapitels extrahieren
            for item in content_items:
                # Struktur kann sein:
                # 1. Direkt: { "library": "...", "params": {...} }
                # 2. Verschachtelt: { "content": { "library": "...", "params": {...} } }
                if "content" in item and isinstance(item.get("content"), dict):
                    content_obj = item["content"]
                    content_library = content_obj.get("library", "")
                    content_params = content_obj.get("params", {})
                else:
                    content_library = item.get("library", "")
                    content_params = item.get("params", {})
                
                if not content_library or not content_params:
                    continue
                
                # Verwende Registry-basierte Extraktion
                extracted = cls.extract_child_content(content_library, content_params)
                
                if extracted:
                    chapter_contents.append(extracted)
            
            # Nur Kapitel mit Inhalt hinzufügen
            if chapter_contents or chapter_title:
                extracted_chapters.append(BookChapter(
                    title=chapter_title,
                    contents=chapter_contents
                ))
        
        if extracted_chapters:
            return cls(
                type=library,
                cover_title=cover_title,
                cover_description=cover_description,
                chapters=extracted_chapters
            )
        
        return None
    
    def to_text(self) -> str:
        """Formatiert InteractiveBook als Text mit Cover und allen Kapiteln."""
        lines = []
        
        # Cover-Informationen
        if self.cover_title:
            lines.append(f"[Interactive Book] {self.cover_title}")
        else:
            lines.append(f"[Interactive Book] {len(self.chapters)} Kapitel")
        
        if self.cover_description:
            lines.append(self.cover_description)
        
        lines.append("")
        
        # Kapitel ausgeben
        for i, chapter in enumerate(self.chapters, start=1):
            if chapter.title:
                lines.append(f"--- Kapitel {i}: {chapter.title} ---")
            else:
                lines.append(f"--- Kapitel {i} ---")
            
            chapter_text = chapter.to_text()
            if chapter_text:
                lines.append(chapter_text)
            
            lines.append("")
        
        return "\n".join(lines)
