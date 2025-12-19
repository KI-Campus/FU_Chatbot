import logging
from dataclasses import dataclass, field
from typing import Union, Optional, Any
from src.loaders.models.hp5activities import extract_library_from_h5p
from src.loaders.models.h5pactivities.h5p_quiz_questions import QuizQuestion, TrueFalseQuestion
from src.loaders.models.h5pactivities.h5p_blanks import FillInBlanksQuestion
from src.loaders.models.h5pactivities.h5p_drag_drop import DragDropQuestion, DragDropText, ImageHotspotQuestion
from src.loaders.models.h5pactivities.h5p_basics import H5PVideo
from src.loaders.models.h5pactivities.h5p_dialogcards import H5PDialogcards
from src.loaders.models.h5pactivities.h5p_flashcards import H5PFlashcards
from src.loaders.models.h5pactivities.h5p_timeline import H5PTimeline
from src.loaders.models.h5pactivities.h5p_summary import Summary as H5PSummary
from src.loaders.models.h5pactivities.h5p_question_set import QuestionSet
from src.loaders.models.hp5activities import strip_html

logger = logging.getLogger(__name__)


# Union-Type für alle unterstützten Inhaltstypen
# Wird durch Forward Reference aktualisiert, da Accordion noch nicht definiert ist
ColumnContent = Union[
    QuizQuestion,
    TrueFalseQuestion,
    FillInBlanksQuestion,
    DragDropQuestion,
    DragDropText,
    ImageHotspotQuestion,
    H5PVideo,
    H5PDialogcards,
    H5PFlashcards,
    H5PTimeline,
    H5PSummary,
    'Accordion',  # Forward Reference, da Accordion weiter unten definiert wird
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
            
            # ImageHotspot
            elif "H5P.ImageHotspot" in content_library:
                extracted = ImageHotspotQuestion.from_h5p_params(content_library, content_params)
            
            # Video
            elif "H5P.Video" in content_library:
                extracted = H5PVideo.from_h5p_params(content_library, content_params)
            
            # Dialogcards
            elif "H5P.Dialogcards" in content_library:
                extracted = H5PDialogcards.from_h5p_params(content_library, content_params)

            # Flashcards
            elif "H5P.Flashcards" in content_library:
                extracted = H5PFlashcards.from_h5p_params(content_library, content_params)
            
            # Timeline
            elif "H5P.Timeline" in content_library:
                extracted = H5PTimeline.from_h5p_params(content_library, content_params)
            
            # AdvancedText / Text
            elif "H5P.AdvancedText" in content_library or "H5P.Text" in content_library:
                # Einfachen Text extrahieren
                text_content = content_params.get("text", "").strip()
                if text_content:
                    extracted = SimpleTextContent(
                        type=content_library,
                        text=text_content
                    )
            
            # Accordion (kann auch innerhalb Column vorkommen)
            elif "H5P.Accordion" in content_library:
                extracted = Accordion.from_h5p_params(content_library, content_params)
            
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
    content: Any  # Beliebiger H5P-Inhaltstyp


@dataclass
class Accordion:
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
                text_content = content_params.get("text", "").strip()
                if text_content:
                    extracted = SimpleTextContent(
                        type=content_library,
                        text=text_content
                    )
            
            # Fallback: Unsupported Typen
            else:
                logger.debug(f"⚠️  H5P-Typ nicht unterstützt in Accordion: {content_library}")
                pass
            
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
    content: Optional[Any] = None  # Das H5P-Content Objekt (QuizQuestion, Text, etc.)

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
class Gamemap:
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
            
                # ImageHotspot
                elif "H5P.ImageHotspot" in content_library:
                    extracted = ImageHotspotQuestion.from_h5p_params(content_library, content_params)
            
                # Video
                elif "H5P.Video" in content_library:
                    extracted = H5PVideo.from_h5p_params(content_library, content_params)
            
                # Dialogcards
                elif "H5P.Dialogcards" in content_library:
                    extracted = H5PDialogcards.from_h5p_params(content_library, content_params)
                
                # Flashcards
                elif "H5P.Flashcards" in content_library:
                    extracted = H5PFlashcards.from_h5p_params(content_library, content_params)

                # Timeline
                elif "H5P.Timeline" in content_library:
                    extracted = H5PTimeline.from_h5p_params(content_library, content_params)
            
                # AdvancedText / Text
                elif "H5P.AdvancedText" in content_library or "H5P.Text" in content_library:
                    text_content = content_params.get("text", "").strip()
                    if text_content:
                        extracted = SimpleTextContent(
                            type=content_library,
                            text=text_content
                        )
            
                # QuestionSet
                elif "H5P.QuestionSet" in content_library:
                    extracted = QuestionSet.from_h5p_params(content_library, content_params)
            
                # Column (auch in Gamemap möglich)
                elif "H5P.Column" in content_library:
                    extracted = Column.from_h5p_params(content_library, content_params)
            
                # Accordion (auch in Gamemap möglich)
                elif "H5P.Accordion" in content_library:
                    extracted = Accordion.from_h5p_params(content_library, content_params)
            
                # Fallback: Unsupported Typen
                else:
                    logger.debug(f"⚠️  H5P-Typ nicht unterstützt in Gamemap: {content_library}")
                    extracted = None
            
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
    contents: list[Any] = field(default_factory=list)

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
class CoursePresentation:
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
        raw_slides = params.get("slides", [])
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

                # Quiztypen
                if "H5P.MultiChoice" in content_library or "H5P.SingleChoiceSet" in content_library:
                    extracted = QuizQuestion.from_h5p_params(content_library, content_params)
                elif "H5P.TrueFalse" in content_library:
                    extracted = TrueFalseQuestion.from_h5p_params(content_library, content_params)
                elif "H5P.Blanks" in content_library:
                    extracted = FillInBlanksQuestion.from_h5p_params(content_library, content_params)
                elif "H5P.DragQuestion" in content_library:
                    extracted = DragDropQuestion.from_h5p_params(content_library, content_params)
                elif "H5P.DragText" in content_library:
                    extracted = DragDropText.from_h5p_params(content_library, content_params)
                elif "H5P.ImageHotspot" in content_library:
                    extracted = ImageHotspotQuestion.from_h5p_params(content_library, content_params)

                # Inhaltstypen
                elif "H5P.Video" in content_library:
                    extracted = H5PVideo.from_h5p_params(content_library, content_params)
                elif "H5P.Dialogcards" in content_library:
                    extracted = H5PDialogcards.from_h5p_params(content_library, content_params)
                elif "H5P.Flashcards" in content_library:
                    extracted = H5PFlashcards.from_h5p_params(content_library, content_params)
                elif "H5P.Timeline" in content_library:
                    extracted = H5PTimeline.from_h5p_params(content_library, content_params)
                elif "H5P.Summary" in content_library:
                    extracted = H5PSummary.from_h5p_params(content_library, content_params)
                elif "H5P.AdvancedText" in content_library or "H5P.Text" in content_library:
                    text_content = content_params.get("text", "").strip()
                    if text_content:
                        extracted = SimpleTextContent(type=content_library, text=text_content)

                # Wrapper innerhalb Slides
                elif "H5P.Column" in content_library:
                    extracted = Column.from_h5p_params(content_library, content_params)
                elif "H5P.Accordion" in content_library:
                    extracted = Accordion.from_h5p_params(content_library, content_params)
                elif "H5P.QuestionSet" in content_library:
                    extracted = QuestionSet.from_h5p_params(content_library, content_params)
                elif "H5P.Gamemap" in content_library or "H5P.GameMap" in content_library:
                    extracted = Gamemap.from_h5p_params("H5P.Gamemap", content_params)
                else:
                    logger.debug(f"⚠️  H5P-Typ nicht unterstützt in CoursePresentation: {content_library}")
                    extracted = None

                if extracted:
                    contents.append(extracted)

            slides.append(CourseSlide(index=idx, contents=contents))

        return cls(type=library, slides=slides) if slides else None

    def to_text(self) -> str:
        if not self.slides:
            return "[CoursePresentation] Keine Slides vorhanden"
        return "\n\n".join(slide.to_text() for slide in self.slides)
