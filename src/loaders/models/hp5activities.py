from pathlib import Path
import re

from pydantic import BaseModel, HttpUrl, root_validator


def strip_html(text: str) -> str:
    """Entfernt HTML-Tags und dekodiert HTML-Entities."""
    if not text:
        return ""
    # Entferne HTML-Tags
    text = re.sub(r'<[^>]+>', '', text)
    # Ersetze HTML-Entities
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&amp;', '&')
    text = text.replace('&quot;', '"')
    # Entferne übermäßige Whitespaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


class H5PActivities(BaseModel):
    id: int
    coursemodule: int
    fileurl: HttpUrl
    filename: Path

    @root_validator(pre=True)
    def validate_fileurl(cls, values):
        values["fileurl"] = values["package"][0]["fileurl"]
        values["filename"] = values["package"][0]["filename"]
        return values