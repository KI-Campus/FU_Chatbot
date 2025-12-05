from enum import StrEnum
from typing import Optional

from llama_index.core import Document
from pydantic import BaseModel, HttpUrl, computed_field

from src.loaders.models.downloadablecontent import DownloadableContent
from src.loaders.models.texttrack import TextTrack
from src.loaders.models.videotime import Video
from src.loaders.models.hp5activities import InteractiveVideo


class ModuleTypes(StrEnum):
    VIDEOTIME = "videotime"
    PAGE = "page"
    H5P = "h5pactivity"


class Module(BaseModel):
    """Lowest level content block of a course. Can be a file, video, hp5, etc."""

    id: int
    visible: int
    name: str
    url: HttpUrl | None = None
    modname: str  # content type
    text: str | None = None
    contents: list[DownloadableContent] | None = None
    videotime: Video | None = None
    transcripts: list[TextTrack] = []
    interactive_video: InteractiveVideo | None = None

    @computed_field  # type: ignore[misc]
    @property
    def type(self) -> Optional[ModuleTypes]:
        match self.modname:
            case "videotime":
                return ModuleTypes.VIDEOTIME
            case "page":
                return ModuleTypes.PAGE
            case "h5pactivity":
                return ModuleTypes.H5P
            case _:
                return None

    def to_document(self, course_id) -> Document:
        text_parts = []
        
        # Name
        text_parts.append(f"Module Name: {self.name}")
        
        # Text-Content
        if self.text is not None:
            text_parts.append(f"\nText: {self.text}")
        
        # Transkript
        if len(self.transcripts) > 0:
            text_parts.append("\nTranscript:")
            text_parts.extend([str(transcript) for transcript in self.transcripts])
        
        # Interactive Video Fragen
        if self.interactive_video and self.interactive_video.interactions:
            text_parts.append("\n--- Quizfragen im Video ---")
            for interaction in self.interactive_video.interactions:
                text_parts.append(interaction.to_text())
        
        text = "\n".join(text_parts)

        metadata = {
            "course_id": course_id,
            "module_id": self.id,
            "fullname": self.name,
            "type": "module",
            "url": str(self.url),
        }

        return Document(text=text, metadata=metadata)
