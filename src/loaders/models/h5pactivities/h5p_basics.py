from dataclasses import dataclass
from typing import Optional
import zipfile
from src.loaders.models.hp5activities import strip_html, extract_library_from_h5p


@dataclass
class Text:
    """Text-Einblendung im Interactive Video."""
    type: str  # z.B. "H5P.Text" oder "H5P.AdvancedText"
    text: str
    
    @classmethod
    def from_h5p_package(cls, module, content: dict, h5p_zip_path: str, **kwargs) -> Optional[str]:
        """
        Handler für standalone H5P.Text.
        Befüllt module.interactive_video mit einem Text-Element als dict.
        """
        library = extract_library_from_h5p(h5p_zip_path) or content.get("library", "")
        params = content
        
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


@dataclass
class H5PVideo:
    """Einfaches H5P.Video (ohne Interaktionen)."""
    type: str  # "H5P.Video"
    video_url: str
    vimeo_id: Optional[str] = None
    transcript: Optional[str] = None  # Transkript wird direkt im Video-Text ausgegeben

    @classmethod
    def from_h5p_package(cls, module, content: dict, h5p_zip_path: str, **kwargs) -> Optional[str]:
        """
        Handler für standalone H5P.Video.
        - Ermittelt die Video-URL (Vimeo/Youtube)
        - Extrahiert Transkript via Vimeo-API (gleiches Verfahren wie InteractiveVideo)
        - Befüllt module.interactive_video
        - Transkript wird direkt im Video-Text ausgegeben (nicht separat unter "Transcript:")
        """
        library = extract_library_from_h5p(h5p_zip_path) or "H5P.Video"
        params = content

        video_obj = cls.from_h5p_params(library, params)
        if not video_obj:
            return "Konnte H5P.Video nicht extrahieren"

        vimeo_service = kwargs.get("vimeo_service")
        video_service = kwargs.get("video_service")

        vimeo_id = None
        texttrack = None
        err_message = None

        # Versuche Vimeo-/YouTube-Parsing wie bei InteractiveVideo
        try:
            if video_service and video_obj.video_url:
                video = video_service(id=0, vimeo_url=video_obj.video_url)
                vimeo_id = video.video_id
        except Exception:
            pass

        # === TRANSKRIPT EXTRAHIEREN ===
        # Versuche VTT-Datei aus H5P-Package zu extrahieren (Fallback)
        fallback_transcript_content = None
        if h5p_zip_path:
            try:
                # Versuche verschiedene mögliche Strukturen für textTracks
                # Möglichkeit 1: params.textTracks.textTrack[0].track.path
                # Möglichkeit 2: params.video.textTracks.videoTrack[0].track.path (wie bei InteractiveVideo)
                vtt_path = None
                
                if "textTracks" in params:
                    if "textTrack" in params["textTracks"]:
                        vtt_path = params["textTracks"]["textTrack"][0].get("track", {}).get("path")
                    elif "videoTrack" in params["textTracks"]:
                        vtt_path = params["textTracks"]["videoTrack"][0].get("track", {}).get("path")
                
                if vtt_path:
                    fallback_transcript_file = f"content/{vtt_path}"
                    with zipfile.ZipFile(h5p_zip_path, "r") as zip_ref:
                        with zip_ref.open(fallback_transcript_file) as vtt_file:
                            fallback_transcript_content = vtt_file.read().decode('utf-8')
            except (KeyError, IndexError, FileNotFoundError, zipfile.BadZipFile):
                # Kein VTT-File im H5P-Package gefunden
                fallback_transcript_content = None

        # Hole Transkript von Vimeo (mit oder ohne Fallback)
        if vimeo_service and vimeo_id:
            texttrack, err_message = vimeo_service.get_transcript(
                vimeo_id, fallback_transcript_content=fallback_transcript_content
            )
        
        # Speichere Transkript direkt im Video-Objekt (nicht in module.transcripts)
        if texttrack and hasattr(texttrack, 'transcript'):
            video_obj.transcript = texttrack.transcript
            video_obj.vimeo_id = vimeo_id

        # Speichere als dict (Dependency Inversion)
        module.interactive_video = {
            "video_url": video_obj.video_url,
            "vimeo_id": vimeo_id,
            "interactions": [video_obj.to_text()],
        }

        return err_message

    @classmethod
    def from_h5p_params(cls, library: str, params: dict) -> Optional['H5PVideo']:
        """Extrahiert H5P.Video aus params (z.B. in Column eingebettet)."""
        sources = params.get("sources", [])
        video_url = None
        if sources and isinstance(sources, list):
            first = sources[0] or {}
            video_url = first.get("path")

        if video_url:
            return cls(type=library, video_url=video_url)
        return None

    def to_text(self) -> str:
        """Gibt Video-Text mit eingebettetem Transkript aus."""
        if self.transcript:
            return f"[Video] Transkript: {self.transcript}"
        return f"[Video] {self.video_url}"