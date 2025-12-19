from dataclasses import dataclass, field
from typing import Optional

from src.loaders.models.hp5activities import strip_html, extract_library_from_h5p


@dataclass
class TimelineEntry:
	start_date: str
	headline: str
	text: str

	def to_text(self) -> str:
		headline_clean = strip_html(self.headline).strip()
		text_clean = strip_html(self.text).strip()
		return f"{self.start_date}: {headline_clean}\n{text_clean}" if text_clean else f"{self.start_date}: {headline_clean}"


@dataclass
class H5PTimeline:
	"""Handler für H5P.Timeline."""
	type: str
	entries: list[TimelineEntry] = field(default_factory=list)

	@classmethod
	def from_h5p_package(cls, module, content: dict, h5p_zip_path: str, **kwargs) -> Optional[str]:
		library = extract_library_from_h5p(h5p_zip_path) or "H5P.Timeline"
		params = content

		timeline = cls.from_h5p_params(library, params)
		if timeline and timeline.entries:
			module.interactive_video = {
				"video_url": "",
				"vimeo_id": None,
				"interactions": [timeline.to_text()],
			}
			return None

		return "Konnte Timeline nicht extrahieren"

	@classmethod
	def from_h5p_params(cls, library: str, params: dict) -> Optional['H5PTimeline']:
		timeline_data = params.get("timeline", {}) or params
		entries_data = timeline_data.get("date", [])
		entries: list[TimelineEntry] = []

		for item in entries_data:
			start_date = item.get("startDate", "").strip()
			headline = item.get("headline", "").strip()
			text = item.get("text", "").strip()
			if start_date or headline or text:
				entries.append(TimelineEntry(start_date=start_date, headline=headline, text=text))

		if entries:
			return cls(type=library, entries=entries)
		return None

	def to_text(self) -> str:
		lines: list[str] = []
		for entry in self.entries:
			lines.append(entry.to_text())
		return "\n\n".join(lines)
