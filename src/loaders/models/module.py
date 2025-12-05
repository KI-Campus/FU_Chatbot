from enum import StrEnum
from typing import Optional, TYPE_CHECKING, Any

from llama_index.core import Document
from pydantic import BaseModel, HttpUrl, computed_field

from src.loaders.models.downloadablecontent import DownloadableContent
from src.loaders.models.texttrack import TextTrack
from src.loaders.models.videotime import Video

if TYPE_CHECKING:
    from src.loaders.models.h5pactivities.h5p_interactive_video import InteractiveVideo
else:
    # Zur Laufzeit: Forward reference als String
    InteractiveVideo = "InteractiveVideo"


class ModuleTypes(StrEnum):
    VIDEOTIME = "videotime"
    PAGE = "page"
    H5P = "h5pactivity"


# H5P Handler Mapping: Library-Name → Handler-Klasse
# Die Handler-Klassen müssen eine statische Methode `from_h5p_package(module, content, h5p_zip_path, **services)` haben
H5P_HANDLERS = {
    "H5P.InteractiveVideo": "src.loaders.models.h5pactivities.h5p_interactive_video.InteractiveVideo",
    "H5P.MultiChoice": "src.loaders.models.h5pactivities.h5p_quiz_questions.QuizQuestion",
    "H5P.SingleChoiceSet": "src.loaders.models.h5pactivities.h5p_quiz_questions.QuizQuestion",
    "H5P.TrueFalse": "src.loaders.models.h5pactivities.h5p_quiz_questions.TrueFalseQuestion",
    "H5P.DragQuestion": "src.loaders.models.h5pactivities.h5p_drag_drop.DragDropQuestion",
    "H5P.Blanks": "src.loaders.models.h5pactivities.h5p_blanks.FillInBlanksQuestion",
    "H5P.Text": "src.loaders.models.h5pactivities.h5p_basics.Text",
    # Weitere H5P-Typen können hier einfach hinzugefügt werden:
    # "H5P.QuestionSet": "src.loaders.models.h5pactivities.h5p_question_set.QuestionSet",
    # "H5P.CoursePresentation": "src.loaders.models.h5pactivities.h5p_course_presentation.CoursePresentation",
}


class Module(BaseModel):
    """Lowest level content block of a course. Can be a file, video, hp5, etc."""

    id: int
    visible: int
    name: str
    url: HttpUrl | None = None
    modname: str  # content type
    h5p_content_type: str | None = None  # H5P library name from content.json
    text: str | None = None
    contents: list[DownloadableContent] | None = None
    videotime: Video | None = None
    transcripts: list[TextTrack] = []
    interactive_video: Optional[Any] = None  # InteractiveVideo - use Any to avoid circular import

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
        
        # Interactive Video Fragen und Summary
        if self.interactive_video and self.interactive_video.interactions:
            text_parts.append("\n--- Interaktive Inhalte im Video ---")
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
