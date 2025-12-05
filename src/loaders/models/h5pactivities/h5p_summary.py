from dataclasses import dataclass
from typing import Optional
from src.loaders.models.hp5activities import strip_html


@dataclass
class Summary:
    """Summary am Ende eines Interactive Videos."""
    type: str  # "H5P.Summary"
    intro: str
    statement_groups: list[list[str]]  # Jede Gruppe: [korrekte Aussage, falsche Aussagen...]
    
    @classmethod
    def from_h5p_summary_data(cls, summary_data: dict) -> Optional['Summary']:
        """Extrahiert Summary aus H5P summary-Struktur (aus interactiveVideo.summary)."""
        if "task" not in summary_data:
            return None
        
        task_params = summary_data["task"].get("params", {})
        intro = task_params.get("intro", "").strip()
        summaries = task_params.get("summaries", [])
        
        statement_groups = []
        for summary_group in summaries:
            statements = summary_group.get("summary", [])
            if statements:
                # Erstes Statement ist korrekt, Rest sind falsch
                clean_statements = [s.strip() for s in statements if s.strip()]
                if clean_statements:
                    statement_groups.append(clean_statements)
        
        if intro or statement_groups:
            return cls(
                type="H5P.Summary",
                intro=intro if intro else "Abschließende Summary-Frage",
                statement_groups=statement_groups
            )
        
        return None
    
    def to_text(self) -> str:
        intro_clean = strip_html(self.intro)
        result = f"[Zusammenfassung] {intro_clean}\n"
        
        for i, statements in enumerate(self.statement_groups, 1):
            result += f"Aussagengruppe {i}:\n"
            if statements:
                correct = strip_html(statements[0])
                result += f" Korrekt: {correct}\n"
                if len(statements) > 1:
                    incorrect = [strip_html(s) for s in statements[1:]]
                    result += f" Falsch: {', '.join(incorrect)}\n"
            result += "\n"
        
        return result.strip()