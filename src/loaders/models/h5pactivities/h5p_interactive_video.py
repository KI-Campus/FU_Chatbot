import logging
from dataclasses import dataclass, field
from typing import Union, Optional
import tempfile
import zipfile
import re
from pydantic import ValidationError

logger = logging.getLogger(__name__)

from src.loaders.models.h5pactivities.h5p_base import H5PContainer
from src.loaders.models.h5pactivities.h5p_quiz_questions import QuizQuestion, TrueFalseQuestion
from src.loaders.models.h5pactivities.h5p_blanks import FillInBlanksQuestion
from src.loaders.models.h5pactivities.h5p_drag_drop import DragDropQuestion, DragDropText
from src.loaders.models.h5pactivities.h5p_basics import Text
from src.loaders.models.h5pactivities.h5p_summary import Summary
from src.loaders.models.h5pactivities.h5p_timeline import H5PTimeline
from src.loaders.models.h5pactivities.h5p_wrappers import Column, Accordion
from src.loaders.models.h5pactivities.h5p_question_set import QuestionSet


# Union-Type für alle Interaktionstypen
VideoInteraction = Union[
    QuizQuestion, 
    TrueFalseQuestion, 
    FillInBlanksQuestion, 
    DragDropQuestion,
    DragDropText,
    Text,
    Column,
    Accordion,
    QuestionSet,
    Summary
]


@dataclass
class InteractiveVideo(H5PContainer):
    """Parsed H5P Interactive Video Content."""
    video_url: str
    vimeo_id: Optional[str] = None
    interactions: list[VideoInteraction] = field(default_factory=list)
    
    @classmethod
    def from_h5p_package(cls, module, content: dict, h5p_zip_path: str, vimeo_service, video_service) -> Optional[str]:
        """
        Extrahiert InteractiveVideo aus H5P Package inkl. Transkript und befüllt Module-Objekt.
        
        Args:
            module: Module-Objekt das befüllt werden soll
            content: Das geladene content.json dict
            h5p_zip_path: Pfad zum H5P ZIP-File (für Fallback-Transkript)
            vimeo_service: Vimeo() Instanz für Transkript-Download
            video_service: Video Klasse für URL-Parsing
            
        Returns:
            Optional[str]: Fehlermeldung oder None
        """
        if "interactiveVideo" not in content:
            return "Kein interactiveVideo in content.json gefunden"
        
        iv = content["interactiveVideo"]
        
        # Video URL extrahieren
        try:
            video_url = iv["video"]["files"][0]["path"]
        except (KeyError, IndexError):
            return "Keine Video-URL gefunden"
        
        # Video-Objekt erstellen (für vimeo_id)
        video = None
        try:
            video = video_service(id=0, vimeo_url=video_url)
        except (ValidationError, Exception):
            # No link to external Video-Service
            pass
        
        if not video:
            return "Kein Vimeo-Video im H5P gefunden"
        
        vimeo_id = video.video_id
        
        # === TRANSKRIPT EXTRAHIEREN ===
        texttrack = None
        err_message = None
        
        # Versuche VTT-Datei aus H5P-Package zu extrahieren
        fallback_transcript_content = None
        try:
            fallback_transcript_file = f"content/{iv['video']['textTracks']['videoTrack'][0]['track']['path']}"
            with zipfile.ZipFile(h5p_zip_path, "r") as zip_ref:
                with zip_ref.open(fallback_transcript_file) as vtt_file:
                    fallback_transcript_content = vtt_file.read().decode('utf-8')
        except (KeyError, IndexError, FileNotFoundError):
            # Kein VTT-File im H5P, versuche trotzdem Vimeo
            fallback_transcript_content = None
        
        # Hole Transkript von Vimeo (mit oder ohne Fallback)
        texttrack, err_message = vimeo_service.get_transcript(
            vimeo_id, fallback_transcript_content=fallback_transcript_content
        )
        
        # === INTERAKTIONEN EXTRAHIEREN ===
        interactions = []
        
        # Prüfe beide mögliche Strukturen
        interaction_list = []
        if "assets" in iv and "interactions" in iv["assets"]:
            interaction_list = iv["assets"]["interactions"]
        elif "interactions" in iv:
            interaction_list = iv["interactions"]
        
        for interaction in interaction_list:
            action = interaction.get("action", {})
            library = action.get("library", "")
            params = action.get("params", {})
            
            # Versuche jede Klasse
            extracted = InteractiveVideo.extract_child_content(library, params)
            
            if extracted:
                interactions.append(extracted)
        
        # === SUMMARY EXTRAHIEREN ===
        if "summary" in iv:
            summary = Summary.from_h5p_summary_data(iv["summary"])
            if summary:
                interactions.append(summary)
        
        # Erstelle InteractiveVideo und befülle Module
        interactive_video = cls(
            video_url=video_url,
            vimeo_id=vimeo_id,
            interactions=interactions
        )
        
        # Speichere als dict in module (Dependency Inversion - module kennt h5pactivities nicht)
        module.interactive_video = interactive_video.to_dict()
        
        if texttrack:
            module.transcripts.append(texttrack)
        
        return err_message
    
    def to_dict(self) -> dict:
        """Konvertiert InteractiveVideo zu dict für Speicherung in Module."""
        # Filtere Accordion-Elemente raus
        from src.loaders.models.h5pactivities.h5p_wrappers import Accordion
        filtered_interactions = [i for i in self.interactions if not isinstance(i, Accordion)]
        
        return {
            "video_url": self.video_url,
            "vimeo_id": self.vimeo_id,
            "interactions": [interaction.to_text() for interaction in filtered_interactions]
        }