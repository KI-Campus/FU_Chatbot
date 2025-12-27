"""
Datenmodell für Moodle Folder Module.

Ein Folder-Modul repräsentiert eine Sammlung von herunterladbaren Dateien (PDF, Audio, etc.).
Funktioniert ähnlich wie Resource, kann aber mehrere Dateien enthalten.
"""

import logging

from pydantic import BaseModel

from src.loaders.models.resource import Resource


class Folder(BaseModel):
    """
    Repräsentiert einen Ordner mit mehreren Dateien aus einem Moodle Folder-Modul.
    
    Folder-Module enthalten typischerweise mehrere Dateien, die alle extrahiert werden.
    Die Implementierung ist sehr ähnlich zu Resource, da beide `contents` als Datei-Liste haben.
    
    Attributes:
        folder_id: ID des Folder-Moduls (aus module.instance)
        module_id: ID des Course-Moduls
        files: Liste der extrahierten Dateien (Resource-Objekte)
        combined_text: Kombinierter Text aller Dateien (für Document-Generierung)
    """
    
    folder_id: int
    module_id: int
    files: list[Resource] = []
    combined_text: str | None = None
    
    def __str__(self) -> str:
        """
        Formatiert alle Dateien im Folder für Document-Generierung.
        
        Bei mehreren Dateien wird jede mit einem Header versehen.
        """
        if not self.files:
            return f"Folder (leer, {self.folder_id})"
        
        if self.combined_text:
            return self.combined_text
        
        # Fallback: Kombiniere alle Dateien
        file_texts = []
        for resource in self.files:
            if resource.extracted_text:
                if len(self.files) > 1:
                    file_texts.append(f"--- Datei: {resource.filename} ---\n{resource.extracted_text}")
                else:
                    file_texts.append(resource.extracted_text)
        
        if file_texts:
            return '\n\n'.join(file_texts)
        
        # Keine extrahierten Texte
        file_names = [f.filename for f in self.files]
        return f"Folder mit {len(self.files)} Datei(en): {', '.join(file_names)}"
    
    @property
    def total_files(self) -> int:
        """Gibt die Anzahl der Dateien im Folder zurück."""
        return len(self.files)
    
    @property
    def total_extracted_chars(self) -> int:
        """Gibt die Gesamtanzahl extrahierter Zeichen zurück."""
        if self.combined_text:
            return len(self.combined_text)
        return sum(len(f.extracted_text or "") for f in self.files)
