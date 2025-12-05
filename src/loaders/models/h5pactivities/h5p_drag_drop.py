from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING
from src.loaders.models.hp5activities import strip_html

if TYPE_CHECKING:
    from src.loaders.models.h5pactivities.h5p_interactive_video import InteractiveVideo


@dataclass
class DragDropQuestion:
    """Drag & Drop-Frage im Interactive Video."""
    type: str  # "H5P.DragQuestion"
    question: str
    categories: list[str]  # Dropzones/Kategorien
    draggable_items: list[str]  # Elemente zum Ziehen
    correct_mappings: dict[str, list[str]] = field(default_factory=dict)  # Kategorie -> Liste von Elementen
    
    @classmethod
    def from_h5p_package(cls, module, content: dict, h5p_zip_path: str, **kwargs) -> Optional[str]:
        """
        Handler für standalone H5P.DragQuestion.
        Befüllt module.interactive_video mit einer Drag&Drop-Aufgabe.
        """
        library = content.get("library", "")
        params = content.get("params", {})
        
        drag_drop = cls.from_h5p_params(library, params)
        
        if drag_drop:
            from src.loaders.models.h5pactivities.h5p_interactive_video import InteractiveVideo
            module.interactive_video = InteractiveVideo(
                video_url="",
                interactions=[drag_drop]
            )
            return None
        
        return "Konnte Drag&Drop-Aufgabe nicht extrahieren"
    
    @classmethod
    def from_h5p_params(cls, library: str, params: dict) -> Optional['DragDropQuestion']:
        """Extrahiert DragDropQuestion aus H5P params."""
        task = params.get("question", {}).get("task", {})
        dropzones = task.get("dropZones", [])
        elements = task.get("elements", [])
        
        question_text = "Ordne die Elemente den Kategorien zu:"
        
        # Extrahiere Kategorien (Dropzones) mit Index
        categories = []
        category_map = {}  # Index -> Label
        for idx, dz in enumerate(dropzones):
            label = dz.get("label", "").strip()
            if label:
                categories.append(label)
                category_map[str(idx)] = label
        
        # Extrahiere ziehbare Elemente mit Index
        draggable_items = []
        element_map = {}  # Index -> Text
        for idx, elem in enumerate(elements):
            text = elem.get("type", {}).get("params", {}).get("text", "").strip()
            if text:
                draggable_items.append(text)
                element_map[str(idx)] = text
        
        # Erstelle korrekte Zuordnungen
        correct_mappings = {}
        for idx, dz in enumerate(dropzones):
            label = dz.get("label", "").strip()
            correct_elem_ids = dz.get("correctElements", [])
            
            if label and correct_elem_ids:
                correct_items = []
                for elem_id in correct_elem_ids:
                    elem_text = element_map.get(str(elem_id))
                    if elem_text:
                        correct_items.append(elem_text)
                
                if correct_items:
                    correct_mappings[label] = correct_items
        
        if categories and draggable_items and correct_mappings:
            return cls(
                type=library,
                question=question_text,
                categories=categories,
                draggable_items=draggable_items,
                correct_mappings=correct_mappings
            )
        
        return None
    
    def to_text(self) -> str:
        question_clean = strip_html(self.question)
        categories_clean = [strip_html(c) for c in self.categories]
        items_clean = [strip_html(i) for i in self.draggable_items]
        
        result = (
            f"[Drag & Drop] {question_clean}\n"
            f"Kategorien: {', '.join(categories_clean)}\n"
            f"Elemente: {', '.join(items_clean)}\n\n"
            f"Korrekte Zuordnung:\n"
        )
        
        for category, items in self.correct_mappings.items():
            category_clean = strip_html(category)
            items_clean_list = [strip_html(item) for item in items]
            result += f"  {category_clean}: {', '.join(items_clean_list)}\n"
        
        return result