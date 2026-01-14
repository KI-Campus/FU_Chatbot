from langfuse.decorators import observe
from llama_index.core.schema import NodeWithScore, TextNode
from llama_index.core.vector_stores import VectorStoreQuery

from src.llm.objects.LLMs import LLM
from src.vectordb.sparse_encoder import BM25SparseEncoder
from src.vectordb.qdrant import VectorDBQdrant, models


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
        
        if use_hybrid:
            self.sparse_encoder = BM25SparseEncoder()
            # For hybrid search, we use direct Qdrant client instead of LlamaIndex wrapper
            self.vector_db = VectorDBQdrant("prod_remote")
            self.collection_name = "web_assistant_hybrid"
        else:
            self.vector_store = VectorDBQdrant("prod_remote").as_llama_vector_store(collection_name="web_assistant_hybrid")

    @observe()
    def retrieve(self, query: str, course_id: int | None = None, module_id: int | None = None) -> list[TextNode]:
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
    
    def _retrieve_dense_only(self, query: str, course_id: int | None, module_id: int | None) -> list[TextNode]:
        """Legacy dense-only retrieval using LlamaIndex wrapper."""
        embedding = self.embedder.get_query_embedding(query)

        conditions = []

        if course_id is None and module_id is None:
            conditions.append(
                models.FieldCondition(
                    key="source",
                    match=models.MatchText(text="Drupal"),
                )
            )

        if course_id is not None:
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

        filter = models.Filter(must=conditions) if conditions else None

        vector_store_query = VectorStoreQuery(query_embedding=embedding, similarity_top_k=self.n_chunks)

        query_result = self.vector_store.query(vector_store_query, qdrant_filters=filter)

        if query_result.nodes is None:
            return []

        for node in query_result.nodes:
            node.text_template = "{metadata_str}\nContent: {content}"

        return query_result.nodes
    
    def _retrieve_hybrid(self, query: str, course_id: int | None, module_id: int | None) -> list[TextNode]:
        """Hybrid retrieval using both dense and sparse vectors.
        
        Qdrant automatically performs fusion (Reciprocal Rank Fusion) when both
        dense and sparse query vectors are provided via prefetch.
        """
        # Generate dense embedding
        dense_embedding = self.embedder.get_query_embedding(query)
        
        # Generate sparse embedding
        sparse_embedding = self.sparse_encoder.encode(query)
        
        # Build filter conditions
        conditions = []
        
        if course_id is None and module_id is None:
            conditions.append(
                models.FieldCondition(
                    key="source",
                    match=models.MatchText(text="Drupal"),
                )
            )
        
        if course_id is not None:
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
        
        query_filter = models.Filter(must=conditions) if conditions else None
        
        # Hybrid search using prefetch + fusion
        # Qdrant performs automatic RRF (Reciprocal Rank Fusion)
        from qdrant_client.models import Prefetch, Query, Fusion, FusionQuery
        
        search_results = self.vector_db.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                Prefetch(
                    query=dense_embedding,
                    using="dense",
                    limit=self.n_chunks * 2,  # Get more candidates for fusion
                    filter=query_filter,
                ),
                Prefetch(
                    query=sparse_embedding,
                    using="sparse",
                    limit=self.n_chunks * 2,
                    filter=query_filter,
                ),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=self.n_chunks,  # Final top-k after fusion
            with_payload=True,
        )
        
        # Convert Qdrant results to TextNodes
        nodes = []
        for result in search_results.points:
            # Extract text from payload
            text = result.payload.get("text", result.payload.get("content", ""))
            
            # Create TextNode
            node = TextNode(
                text=text,
                id_=str(result.id),
                metadata=result.payload,
                score=result.score if hasattr(result, 'score') else None,
            )
            
            # Set template for LLM context
            node.text_template = "{metadata_str}\nContent: {content}"
            
            nodes.append(node)
        
        return nodes
