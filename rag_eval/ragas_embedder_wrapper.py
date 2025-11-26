# ragas_embedder_wrapper.py

from src.embedder.multilingual_e5_large import MultilingualE5LargeEmbedder

class RagasE5Embedder:
    """
    Adapter so RAGAS korrekt mit unserem MultilingualE5LargeEmbedder umgehen kann.
    
    RAGAS erwartet:
        - embed_query(str) -> list[float]
        - embed_documents(list[str]) -> list[list[float]]

    Dein Embedder macht:
        embed(text: str, type="query" | "passage") -> list[float]
    """

    def __init__(self):
        self.model = MultilingualE5LargeEmbedder()

    def embed_query(self, text: str):
        """RAGAS ruft dies für Frage-Embeddings auf."""
        return self.model.embed(text, type="query")

    def embed_documents(self, texts: list[str]):
        """RAGAS ruft dies für Kontext-Embeddings auf."""
        return [self.model.embed(t, type="passage") for t in texts]

    # OPTIONAL: RAGAS fallback 
    def embed(self, texts):
        """Fallback für manche internen RAGAS Calls (z. B. AnswerRelevancy)."""
        if isinstance(texts, str):
            return [self.embed_query(texts)]
        return [self.embed_query(t) for t in texts]
