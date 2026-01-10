"""
Glossary models for Moodle glossary module type.
Handles extraction of glossary entries with concepts and definitions.
"""

from pydantic import BaseModel, field_validator
from src.loaders.helper import process_html_summaries


class GlossaryEntry(BaseModel):
    """Single glossary entry with concept and definition."""
    
    id: int
    concept: str
    definition: str
    
    @field_validator("definition")
    @classmethod
    def clean_html(cls, definition: str) -> str:
        """Remove HTML tags from definition text."""
        if not definition:
            return ""
        return process_html_summaries(definition)
    
    def __str__(self) -> str:
        """Format entry as: Concept: [concept]\nDefinition: [definition]"""
        return f"{self.concept}: {self.definition}"


class Glossary(BaseModel):
    """Collection of glossary entries for a module."""
    
    glossary_id: int
    module_id: int
    entries: list[GlossaryEntry] = []
    
    def __str__(self) -> str:
        """Format all entries as newline-separated string."""
        if not self.entries:
            return ""
        return "\n\n".join([str(entry) for entry in self.entries])
    
    @property
    def total_entries(self) -> int:
        """Return total number of entries."""
        return len(self.entries)
