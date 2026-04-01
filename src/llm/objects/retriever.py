from langfuse.decorators import observe
from qdrant_client.models import Prefetch, Fusion, FusionQuery

from src.llm.objects.LLMs import LLM
from src.vectordb.qdrant import VectorDBQdrant, models
from src.api.models.serializable_text_node import SerializableTextNode


class KiCampusRetriever:
    def __init__(self, use_hybrid: bool = True, n_chunks: int = 10):
        """Initialize retriever with optional hybrid search.
        
        Args:
            use_hybrid: If True, uses both dense and sparse vectors for retrieval.
                       If False, uses only dense vectors (legacy mode).
            n_chunks: Number of chunks to retrieve from vector database.
        """
        self.use_hybrid = use_hybrid
        self.n_chunks = n_chunks
        self.embedder = LLM().get_embedder()
        self.sparse_encoder = None
        self.vector_db = VectorDBQdrant("prod_remote")
        self.collection_name = "web_assistant_hybrid"
        
        if use_hybrid:
            try:
                from fastembed import SparseTextEmbedding

                self.sparse_encoder = SparseTextEmbedding("Qdrant/bm42-all-minilm-l6-v2-attentions")
            except Exception as e:
                # Fastembed/onnxruntime can fail on some Windows setups.
                # Fall back to dense retrieval so chat remains usable.
                print(f"Hybrid retrieval unavailable ({e}). Falling back to dense-only retrieval.")
                self.use_hybrid = False

    @observe()
    def retrieve(self, query: str, course_id: int | None = None, module_id: int | None = None) -> list[SerializableTextNode]:
        """Retrieve relevant documents using hybrid search (dense + sparse vectors).
        
        Args:
            query: Search query
            course_id: Optional filter by course ID
            module_id: Optional filter by module ID
            
        Returns:
            List of relevant TextNodes
        """
        if self.use_hybrid:
            return self._retrieve_hybrid(query, course_id, module_id)
        else:
            return self._retrieve_dense_only(query, course_id, module_id)
    
    def _build_filter(self, course_id: int | list[int] | tuple[int, ...] | None, module_id: int | None):
        """Build Qdrant payload filter shared by dense and hybrid retrieval."""
        conditions = []

        if course_id is None and module_id is None:
            conditions.append(
                models.FieldCondition(
                    key="source",
                    match=models.MatchValue(value="Drupal"),
                )
            )

        if course_id is not None:
            # allow list/tuple of course_ids; falls back to single value
            if isinstance(course_id, (list, tuple)):
                conditions.append(
                    models.FieldCondition(
                        key="course_id",
                        match=models.MatchAny(any=list(course_id)),
                    )
                )
            else:
                conditions.append(
                    models.FieldCondition(
                        key="course_id",
                        match=models.MatchValue(value=course_id),
                    )
                )

        if module_id is not None:
            conditions.append(
                models.FieldCondition(
                    key="module_id",
                    match=models.MatchValue(value=module_id),
                )
            )

        return models.Filter(must=conditions) if conditions else None

    def _points_to_serializable_nodes(self, points) -> list[SerializableTextNode]:
        """Convert Qdrant search points into SerializableTextNodes."""
        nodes = []

        for result in points:
            text = result.payload.get("text", result.payload.get("content", ""))
            metadata = {k: v for k, v in result.payload.items() if k not in ("text", "content")}
            nodes.append(
                SerializableTextNode(
                    text=text,
                    id_=str(result.id),
                    metadata=metadata,
                    score=result.score if hasattr(result, "score") else None,
                )
            )

        return nodes

    def _retrieve_dense_only(self, query: str, course_id: int | list[int] | tuple[int, ...] | None, module_id: int | None) -> list[SerializableTextNode]:
        """Dense-only retrieval using named vector 'dense'."""

        dense_embedding = self.embedder.get_query_embedding(query)
        query_filter = self._build_filter(course_id, module_id)

        search_results = self.vector_db.client.query_points(
            collection_name=self.collection_name,
            query=dense_embedding,
            using="dense",
            query_filter=query_filter,
            limit=self.n_chunks,
            with_payload=True,
        )

        return self._points_to_serializable_nodes(search_results.points)
    
    def _retrieve_hybrid(self, query: str, course_id: int | list[int] | tuple[int, ...] | None, module_id: int | None) -> list[SerializableTextNode]:
        """Hybrid retrieval using both dense and sparse vectors.
        
        Qdrant automatically performs fusion (Reciprocal Rank Fusion) when both
        dense and sparse query vectors are provided via prefetch.
        """
        # Generate dense embedding
        dense_embedding = self.embedder.get_query_embedding(query)
        
        # Generate sparse embedding
        try:
            sparse_result = list(self.sparse_encoder.embed([query]))[0]
            sparse_embedding = models.SparseVector(
                indices=sparse_result.indices.tolist(),
                values=sparse_result.values.tolist()
            )
        except Exception as e:
            print(f"Hybrid sparse embedding failed ({e}). Falling back to dense-only retrieval for this request.")
            return self._retrieve_dense_only(query, course_id, module_id)
        
        query_filter = self._build_filter(course_id, module_id)
        
        # Hybrid search using prefetch + fusion
        # Qdrant performs automatic RRF (Reciprocal Rank Fusion)
        
        search_results = self.vector_db.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                Prefetch(
                    query=dense_embedding,
                    using="dense",
                    limit=self.n_chunks * 3,  # Get more candidates for fusion
                    filter=query_filter,
                ),
                Prefetch(
                    query=sparse_embedding,
                    using="sparse",
                    limit=self.n_chunks * 3,  # Get more candidates for fusion
                    filter=query_filter,
                ),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=self.n_chunks,  # Final top-k after fusion
            with_payload=True,
        )
        
        return self._points_to_serializable_nodes(search_results.points)