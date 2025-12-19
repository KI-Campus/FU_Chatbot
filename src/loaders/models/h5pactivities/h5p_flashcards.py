from dataclasses import dataclass, field
from typing import Optional

from src.loaders.models.hp5activities import strip_html, extract_library_from_h5p


@dataclass
class Flashcard:
	text: str
	answer: str

	def to_text(self) -> str:
		text_clean = strip_html(self.text).strip()
		answer_clean = strip_html(self.answer).strip()
		return f"{text_clean}: {answer_clean}"


@dataclass
class H5PFlashcards:
	"""Handler für H5P.Flashcards.

	Erwartet params mit Feld 'cards': [{text, answer, ...}]
	Gibt pro Karte genau eine Zeile aus: "text: answer" ohne Leerzeile dazwischen.
	"""
	type: str
	cards: list[Flashcard] = field(default_factory=list)

	@classmethod
	def from_h5p_package(cls, module, content: dict, h5p_zip_path: str, **kwargs) -> Optional[str]:
		# Bei standalone Flashcards ist content direkt die Struktur mit cards
		# NICHT unter params wie bei eingebetteten Inhalten
		library = extract_library_from_h5p(h5p_zip_path) or "H5P.Flashcards"
		params = content

		flashcards = cls.from_h5p_params(library, params)

		if flashcards and flashcards.cards:
			module.interactive_video = {
				"video_url": "",
				"vimeo_id": None,
				"interactions": [flashcards.to_text()],
			}
			return None

		return "Konnte Flashcards nicht extrahieren"

	@classmethod
	def from_h5p_params(cls, library: str, params: dict) -> Optional['H5PFlashcards']:
		cards_data = params.get("cards", [])
		cards: list[Flashcard] = []

		for item in cards_data:
			text = item.get("text", "")
			answer = item.get("answer", "")
			if text or answer:
				cards.append(Flashcard(text=text, answer=answer))

		if cards:
			return cls(type=library, cards=cards)
		return None

	def to_text(self) -> str:
		# Eine Zeile pro Karte, keine Leerabsätze
		return "\n".join(card.to_text() for card in self.cards)

