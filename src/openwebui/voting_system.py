"""
Arena Voting System für KI-Campus Chatbot Benchmarking.

Speichert Vergleiche zwischen kicampus-original und kicampus-improved.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field


class ArenaComparison(BaseModel):
    """Ein einzelner Arena-Vergleich zwischen zwei Modellen."""
    
    model_config = {"extra": "allow"}  # Allow extra fields for backwards compatibility
    
    id: str = Field(description="Unique ID für diesen Vergleich")
    question: str = Field(description="Die Frage die gestellt wurde")
    timestamp: str = Field(description="ISO timestamp wann die Frage gestellt wurde")
    
    model_a: str = Field(description="Name des ersten Modells")
    answer_a: str = Field(description="Antwort von Modell A")
    
    model_b: str = Field(description="Name des zweiten Modells")
    answer_b: str = Field(description="Antwort von Modell B")
    
    vote: Optional[Literal["A", "B", "tie", "both_bad"]] = Field(default=None, description="Voting-Ergebnis")
    vote_timestamp: Optional[str] = Field(default=None, description="Wann wurde gevotet")
    comment: Optional[str] = Field(default=None, description="Optional: Kommentar zum Vote")
    subset_id: Optional[int] = Field(default=None, description="Subset 1-4 für User-Assignment")


class VotingStorage:
    """Verwaltet das Speichern und Laden von Arena Comparisons."""
    
    def __init__(self, storage_file: str = "arena_votes.jsonl"):
        """
        Args:
            storage_file: Pfad zur JSONL Datei (jede Zeile = ein JSON Objekt)
        """
        self.storage_file = Path(storage_file)
        # Erstelle Datei wenn nicht existiert
        if not self.storage_file.exists():
            self.storage_file.parent.mkdir(parents=True, exist_ok=True)
            self.storage_file.touch()
    
    def save_comparison(self, comparison: ArenaComparison) -> None:
        """Speichert einen neuen Vergleich (append-only)."""
        with open(self.storage_file, "a", encoding="utf-8") as f:
            f.write(comparison.model_dump_json() + "\n")
    
    def load_all_comparisons(self) -> List[ArenaComparison]:
        """Lädt alle gespeicherten Vergleiche."""
        comparisons = []
        if not self.storage_file.exists():
            return comparisons
        
        with open(self.storage_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    comparisons.append(ArenaComparison.model_validate_json(line))
        
        return comparisons
    
    def get_comparison_by_id(self, comparison_id: str) -> Optional[ArenaComparison]:
        """Findet einen spezifischen Vergleich anhand der ID."""
        comparisons = self.load_all_comparisons()
        for comp in comparisons:
            if comp.id == comparison_id:
                return comp
        return None
    
    def update_vote(self, comparison_id: str, vote: Literal["A", "B", "tie", "both_bad"], comment: Optional[str] = None) -> bool:
        """
        Updated einen existierenden Vergleich mit Vote-Informationen.
        
        Returns:
            True wenn erfolgreich, False wenn ID nicht gefunden
        """
        comparisons = self.load_all_comparisons()
        found = False
        
        for comp in comparisons:
            if comp.id == comparison_id:
                comp.vote = vote
                comp.vote_timestamp = datetime.utcnow().isoformat()
                if comment:
                    comp.comment = comment
                found = True
                break
        
        if not found:
            return False
        
        # Überschreibe Datei mit updated comparisons
        with open(self.storage_file, "w", encoding="utf-8") as f:
            for comp in comparisons:
                f.write(comp.model_dump_json() + "\n")
        
        return True
    
    def get_comparisons_by_subset(self, subset_id: int) -> List[ArenaComparison]:
        """Filtert Vergleiche nach Subset-ID."""
        all_comparisons = self.load_all_comparisons()
        return [c for c in all_comparisons if c.subset_id == subset_id]
    
    def assign_subset_round_robin(self) -> int:
        """Weist ein Subset zu basierend auf Vote-Counts (Round-Robin für faire Verteilung)."""
        comparisons = self.load_all_comparisons()
        
        # Zähle Votes pro Subset
        subset_votes = {1: 0, 2: 0, 3: 0, 4: 0}
        for c in comparisons:
            if c.subset_id and c.vote:
                subset_votes[c.subset_id] = subset_votes.get(c.subset_id, 0) + 1
        
        # Weise Subset mit wenigsten Votes zu
        return min(subset_votes, key=subset_votes.get)
    
    def get_statistics(self) -> Dict[str, any]:
        """Berechnet Statistiken über alle Votes."""
        comparisons = self.load_all_comparisons()
        
        total = len(comparisons)
        voted = sum(1 for c in comparisons if c.vote is not None)
        unvoted = total - voted
        
        votes_a = sum(1 for c in comparisons if c.vote == "A")
        votes_b = sum(1 for c in comparisons if c.vote == "B")
        votes_tie = sum(1 for c in comparisons if c.vote == "tie")
        votes_both_bad = sum(1 for c in comparisons if c.vote == "both_bad")
        
        # Finde häufigste Modell-Namen
        model_names = set()
        for c in comparisons:
            model_names.add(c.model_a)
            model_names.add(c.model_b)
        
        return {
            "total_comparisons": total,
            "voted": voted,
            "unvoted": unvoted,
            "votes_for_a": votes_a,
            "votes_for_b": votes_b,
            "votes_tie": votes_tie,
            "votes_both_bad": votes_both_bad,
            "win_rate_a": votes_a / voted if voted > 0 else 0,
            "win_rate_b": votes_b / voted if voted > 0 else 0,
            "tie_rate": votes_tie / voted if voted > 0 else 0,
            "both_bad_rate": votes_both_bad / voted if voted > 0 else 0,
            "models_seen": list(model_names),
        }
    
    def export_to_json(self, output_file: str) -> None:
        """Exportiert alle Comparisons als schönes JSON Array."""
        comparisons = self.load_all_comparisons()
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(
                [c.model_dump() for c in comparisons],
                f,
                indent=2,
                ensure_ascii=False
            )


# Global Storage Instance
default_storage = VotingStorage(
    storage_file=os.path.join(os.path.dirname(__file__), "data", "arena_votes.jsonl")
)
