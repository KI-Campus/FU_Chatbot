from dataclasses import dataclass, field
from typing import Optional

from src.loaders.models.hp5activities import strip_html, extract_library_from_h5p


@dataclass
class DialogCard:
    """Eine einzelne Dialog-Karte mit Vorder- und Rückseite."""
    text: str
    answer: str

    def to_text(self) -> str:
        """Formatiert die Karte als 'text: answer'."""
        clean_text = strip_html(self.text).strip()
        clean_answer = strip_html(self.answer).strip()
        return f"{clean_text}: {clean_answer}"


@dataclass
class H5PDialogcards:
    """H5P.Dialogcards - Kartenset zum Lernen."""
    type: str  # "H5P.Dialogcards"
    cards: list[DialogCard] = field(default_factory=list)

    @classmethod
    def from_h5p_package(cls, module, content: dict, h5p_zip_path: str, **kwargs) -> Optional[str]:
        """
        Handler für standalone H5P.Dialogcards.
        Extrahiert alle Dialog-Karten und befüllt module.interactive_video.
        """
        library =  extract_library_from_h5p(h5p_zip_path)
        params = content

        dialogcards = cls.from_h5p_params(library, params)

        if dialogcards:
            # Speichere als dict (Dependency Inversion)
            module.interactive_video = {
                "video_url": "",
                "vimeo_id": None,
                "interactions": [dialogcards.to_text()],
            }
            return None

        return "Konnte H5P.Dialogcards nicht extrahieren"

    @classmethod
    def from_h5p_params(cls, library: str, params: dict) -> Optional['H5PDialogcards']:
        """Extrahiert H5P.Dialogcards aus params (z.B. in Column eingebettet)."""
        dialogs = params.get("dialogs", [])

        if not dialogs:
            return None

        cards = []
        for dialog in dialogs:
            if isinstance(dialog, dict):
                text = dialog.get("text", "")
                answer = dialog.get("answer", "")
                if text and answer:
                    cards.append(DialogCard(text=text, answer=answer))

        if cards:
            return cls(type=library, cards=cards)
        return None

    def to_text(self) -> str:
        """Gibt alle Karten formatiert aus."""
        if not self.cards:
            return "[Dialogcards] Keine Karten vorhanden"

        card_texts = [card.to_text() for card in self.cards]
        return "\n".join(card_texts)
