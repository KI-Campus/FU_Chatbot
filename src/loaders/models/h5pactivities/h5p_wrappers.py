import logging
from dataclasses import dataclass, field
from typing import Optional
from src.loaders.models.hp5activities import extract_library_from_h5p, strip_html
from src.loaders.models.h5pactivities.h5p_base import H5PContainer, H5PContentBase
from src.loaders.models.h5pactivities.h5p_basics import H5PVideo

logger = logging.getLogger(__name__)


@dataclass
class Column(H5PContainer):
    """
    H5P.Column - Extrem oberflächlicher Wrapper für mehrere H5P-Inhalte.
    
    Column ordnet verschiedene H5P-Inhalte untereinander an.
    Es können beliebige H5P-Typen in beliebiger Reihenfolge vorkommen.
    """
    type: str = "H5P.Column"
    contents: list[H5PContentBase] = field(default_factory=list)
    
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
        library = extract_library_from_h5p(h5p_zip_path) or "H5P.Column"
        
        column = cls.from_h5p_params(library, content)
        
        if column and column.contents:
            # Versuche Transkripte für eingebettete Videos zu extrahieren (gleiche Logik wie InteractiveVideo)
            vimeo_service = kwargs.get("vimeo_service")
            video_service = kwargs.get("video_service")
            if vimeo_service and video_service:
                for c in column.contents:
                    if isinstance(c, H5PVideo) and getattr(c, "video_url", None):
                        try:
                            video = video_service(id=0, vimeo_url=c.video_url)
                            vimeo_id = video.video_id
                            if vimeo_id:
                                texttrack, _ = vimeo_service.get_transcript(vimeo_id)
                                if texttrack and hasattr(texttrack, 'transcript'):
                                    # Speichere Transkript direkt im H5PVideo-Objekt
                                    c.transcript = texttrack.transcript
                                    c.vimeo_id = vimeo_id
                        except Exception:
                            pass

            # Speichere als dict (Dependency Inversion)
            # Alle Inhalte werden als separate Texte gespeichert
            # Accordion.to_text() gibt leeren String zurück, um Rauschen im RAG zu vermeiden
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
            
            # AdvancedText / Text - Special case für inline SimpleTextContent
            if "H5P.AdvancedText" in content_library or "H5P.Text" in content_library:
                # Einfachen Text extrahieren
                text_content = content_params.get("text", "").strip()
                if text_content:
                    extracted = SimpleTextContent(
                        type=content_library,
                        text=text_content
                    )
            else:
                # Alle anderen Typen via Registry
                extracted = Column.extract_child_content(content_library, content_params)
            
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
            text_output = content.to_text() if hasattr(content, 'to_text') else str(content)
            # Überspringe leere Outputs (z.B. von Accordion)
            if text_output.strip():
                lines.append(f"--- Inhalt {i} ---")
                lines.append(text_output)
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


@dataclass
class AccordionPanel:
    """Ein Panel innerhalb eines H5P.Accordion."""
    title: str
    content: H5PContentBase  # Beliebiger H5P-Inhaltstyp


@dataclass
class Accordion(H5PContainer):
    """
    H5P.Accordion - Accordion-ähnlicher Wrapper für mehrere H5P-Inhalte mit Titeln.
    
    Accordion organisiert verschiedene H5P-Inhalte in erweiterbaren Panels mit Titeln.
    Es können beliebige H5P-Typen in beliebiger Reihenfolge vorkommen.
    """
    type: str = "H5P.Accordion"
    panels: list[AccordionPanel] = field(default_factory=list)
    
    @classmethod
    def from_h5p_package(cls, module, content: dict, h5p_zip_path: str, **kwargs) -> Optional[str]:
        """
        Handler für standalone H5P.Accordion.
        Befüllt module.interactive_video mit allen Panels aus dem Accordion.
        
        Args:
            module: Module-Objekt zum Befüllen
            content: Geladenes content.json dict
            h5p_zip_path: Pfad zum H5P ZIP-File (nicht verwendet)
            **kwargs: Zusätzliche Services (nicht verwendet)
            
        Returns:
            Optional[str]: Fehlermeldung oder None
        """
        library = extract_library_from_h5p(h5p_zip_path) or "H5P.Accordion"
        
        accordion = cls.from_h5p_params(library, content)
        
        if accordion and accordion.panels:
            # Speichere als dict (Dependency Inversion)
            # Alle Panels werden als separate Texte gespeichert
            module.interactive_video = {
                "video_url": "",
                "vimeo_id": None,
                "interactions": [panel_text for panel_text in accordion.to_texts()]
            }
            return None
        
        return "Konnte Accordion nicht extrahieren oder keine Panels gefunden"
    
    @classmethod
    def from_h5p_params(cls, library: str, params: dict) -> Optional['Accordion']:
        """
        Extrahiert Accordion aus H5P params.
        
        Iteriert durch alle panels und versucht, den passenden Handler
        für jeden Panel-Inhaltstyp zu finden.
        """
        extracted_panels = []
        
        for panel_data in params.get("panels", []):
            panel_title = panel_data.get("title", "Panel").strip()
            content_data = panel_data.get("content", {})
            
            if not content_data:
                continue
            
            content_library = content_data.get("library", "")
            content_params = content_data.get("params", {})
            
            if not content_library or not content_params:
                continue
            
            # Verwende bestehende Handler für jeden unterstützten Typ
            extracted = None
            
            # AdvancedText / Text - Special case für inline SimpleTextContent
            if "H5P.AdvancedText" in content_library or "H5P.Text" in content_library:
                text_content = content_params.get("text", "").strip()
                if text_content:
                    extracted = SimpleTextContent(
                        type=content_library,
                        text=text_content
                    )
            else:
                # Alle anderen Typen via Registry
                extracted = Accordion.extract_child_content(content_library, content_params)
            
            if extracted:
                extracted_panels.append(AccordionPanel(title=panel_title, content=extracted))
        
        if extracted_panels:
            return cls(
                type=library,
                panels=extracted_panels
            )
        
        return None
    
    def to_texts(self) -> list[str]:
        """Formatiert Accordion als Liste von Panel-Texten."""
        texts = []
        
        for i, panel in enumerate(self.panels, start=1):
            lines = []
            lines.append(f"[Accordion Panel {i}] {panel.title}")
            if hasattr(panel.content, 'to_text'):
                lines.append(panel.content.to_text())
            else:
                lines.append(str(panel.content))
            texts.append("\n".join(lines))
        
        return texts
    
    def to_text(self) -> str:
        """
        Formatiert Accordion-Inhalte ohne Headerzeile.
        Nur die Panel-Titel und deren Inhalte werden ausgegeben.
        """
        return "\n".join(self.to_texts())



@dataclass
class GamemapStage:
    """Ein Stage/Element in einer Gamemap."""
    label: str
    content: Optional[H5PContentBase] = None  # Das H5P-Content Objekt (QuizQuestion, Text, etc.)

    def to_text(self) -> str:
        """Formatiert den Stage mit Label und Inhalt."""
        lines = []
        lines.append(f"[Stage] {self.label}")
        if self.content and hasattr(self.content, 'to_text'):
            lines.append(self.content.to_text())
        elif self.content:
            lines.append(str(self.content))
        return "\n".join(lines)


@dataclass
class Gamemap(H5PContainer):
    """
    H5P.Gamemap - Interaktive Karte mit mehreren Stages/Elementen.

    Gamemap ist ein Wrapper-Typ, der mehrere H5P-Inhalte als Stages
    auf einer visuellen Karte anordnet. Jeder Stage hat einen Label und einen Content.
    """
    type: str = "H5P.Gamemap"
    stages: list[GamemapStage] = field(default_factory=list)
    
    @classmethod
    def from_h5p_package(cls, module, content: dict, h5p_zip_path: str, **kwargs) -> Optional[str]:
        """
        Handler für standalone H5P.Gamemap.
        Extrahiert alle Stages aus gamemapSteps.gamemap.elements und befüllt module.interactive_video.
        """
        library = extract_library_from_h5p(h5p_zip_path) or "H5P.Gamemap"
        gamemap = cls.from_h5p_params(library, content)
    
        if gamemap and gamemap.stages:
            # Speichere als dict (Dependency Inversion)
            module.interactive_video = {
                "video_url": "",
                "vimeo_id": None,
                "interactions": [gamemap.to_text()],
            }
            return None
    
        return "Konnte H5P.Gamemap nicht extrahieren"

    @classmethod
    def from_h5p_params(cls, library: str, params: dict) -> Optional['Gamemap']:
        """
        Extrahiert H5P.Gamemap aus params.
    
        Verarbeitet die Struktur: params.gamemapSteps.gamemap.elements[]
        """
        try:
            # Navigiere zur elements-Liste
            gamemap_steps = params.get("gamemapSteps", {})
            gamemap_data = gamemap_steps.get("gamemap", {})
            elements = gamemap_data.get("elements", [])
        
            if not elements:
                return None
        
            stages = []
        
            for element in elements:
                if not isinstance(element, dict):
                    continue
            
                # Extrahiere Label
                label = element.get("label", "Unnamed Stage")
            
                # Extrahiere contentType
                content_data = element.get("contentType", {})
                content_library = content_data.get("library", "")
                content_params = content_data.get("params", {})
            
                if not content_library or not content_params:
                    # Fallback: nur Label ohne Content
                    stages.append(GamemapStage(label=label, content=None))
                    continue
            
                # Versuche den passenden Handler zu finden
                extracted = None
            
                # AdvancedText / Text - Special case für inline SimpleTextContent
                if "H5P.AdvancedText" in content_library or "H5P.Text" in content_library:
                    text_content = content_params.get("text", "").strip()
                    if text_content:
                        extracted = SimpleTextContent(
                            type=content_library,
                            text=text_content
                        )
                else:
                    # Alle anderen Typen via Registry
                    extracted = Gamemap.extract_child_content(content_library, content_params)
            
                # Füge Stage hinzu (mit oder ohne extrahierten Content)
                stages.append(GamemapStage(label=label, content=extracted))
        
            if stages:
                return cls(type=library, stages=stages)
    
        except Exception as e:
            logger.debug(f"Fehler beim Parsen von Gamemap: {e}")
    
        return None

    def to_text(self) -> str:
        """Formatiert alle Stages in der Gamemap."""
        if not self.stages:
            return "[Gamemap] Keine Stages vorhanden"
    
        stage_texts = [stage.to_text() for stage in self.stages]
        return "\n\n".join(stage_texts)


@dataclass
class CourseSlide:
    """Eine einzelne Slide innerhalb von H5P.CoursePresentation."""
    index: int
    contents: list[H5PContentBase] = field(default_factory=list)

    def to_text(self) -> str:
        lines = []
        lines.append(f"[Seite {self.index}]:")
        for content in self.contents:
            if hasattr(content, 'to_text'):
                text_output = content.to_text()
            else:
                text_output = str(content)
            if text_output.strip():
                lines.append(text_output)
        return "\n".join(lines)


@dataclass
class CoursePresentation(H5PContainer):
    """
    H5P.CoursePresentation – Wrapper für Slides mit diversen H5P-Elementen.

    Jede Slide enthält eine Liste von Elementen (actions), die wiederum eine
    `library` und `params` besitzen. Wir extrahieren alle unterstützten Typen
    und geben sie je Slide mit Präfix "[Seite N]:" aus.
    """
    type: str = "H5P.CoursePresentation"
    slides: list[CourseSlide] = field(default_factory=list)

    @classmethod
    def from_h5p_package(cls, module, content: dict, h5p_zip_path: str, **kwargs) -> Optional[str]:
        """
        Handler für standalone H5P.CoursePresentation.
        Befüllt `module.interactive_video` mit den Slide-Texten.
        """
        library = extract_library_from_h5p(h5p_zip_path) or "H5P.CoursePresentation"
        cp = cls.from_h5p_params(library, content)

        if cp and cp.slides:
            module.interactive_video = {
                "video_url": "",
                "vimeo_id": None,
                "interactions": [slide.to_text() for slide in cp.slides],
            }
            return None

        return "Konnte H5P.CoursePresentation nicht extrahieren oder keine Slides gefunden"

    @classmethod
    def from_h5p_params(cls, library: str, params: dict) -> Optional['CoursePresentation']:
        """Extrahiert Slides und deren Elemente aus den H5P params."""
        presentation = params.get("presentation", {})
        raw_slides = presentation.get("slides", [])
        if not raw_slides:
            return None

        slides: list[CourseSlide] = []

        for idx, slide in enumerate(raw_slides, start=1):
            contents: list[Any] = []
            for element in slide.get("elements", []):
                action = element.get("action", {})
                content_library = action.get("library", "")
                content_params = action.get("params", {})

                if not content_library or not isinstance(content_params, dict):
                    continue

                extracted = None

                # AdvancedText / Text - Special case für inline SimpleTextContent
                if "H5P.AdvancedText" in content_library or "H5P.Text" in content_library:
                    text_content = content_params.get("text", "").strip()
                    if text_content:
                        extracted = SimpleTextContent(type=content_library, text=text_content)
                else:
                    # Alle anderen Typen via Registry
                    extracted = CoursePresentation.extract_child_content(content_library, content_params)

                if extracted:
                    contents.append(extracted)

            slides.append(CourseSlide(index=idx, contents=contents))

        return cls(type=library, slides=slides) if slides else None

    def to_text(self) -> str:
        if not self.slides:
            return "[CoursePresentation] Keine Slides vorhanden"
        return "\n\n".join(slide.to_text() for slide in self.slides)
