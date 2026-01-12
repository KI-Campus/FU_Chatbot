import os
import sys
from typing import List

from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
from qdrant_client.http.models import Distance, PointStruct, VectorParams, SparseVectorParams
from qdrant_client.http.api_client import ResponseHandlingException

from src.env import env

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)


class VectorDBQdrant:
    def __init__(self, version: str = "prod_remote"):
        self.version = version
        if version == "memory":
            self.client = QdrantClient(":memory:")
        elif version == "disk":
            self.client = QdrantClient("localhost", port=6333)
            try:
                _ = self.client.get_collections()
            except ResponseHandlingException as e:
                print("Qdrant container not running? Run:")
                print(
                    "docker run -p 6333:6333 -p 6334:6334 -v $(pwd)/qdrant_storage:/qdrant/storage:z qdrant/qdrant:v1.6.1"
                )
                raise e
        # Longer timeout for dev, because container app is scaled down to 0 instances
        elif version == "dev_remote":
            # Prefer dedicated DEV_QDRANT_* settings; fall back to generic QDRANT_*
            try:
                url = env.DEV_QDRANT_URL
                api_key = env.DEV_QDRANT_API_KEY
            except AttributeError:
                url = env.QDRANT_URL
                api_key = env.QDRANT_API_KEY

            self.client = QdrantClient(url=url, port=443, https=True, timeout=120, api_key=api_key)
            _ = self.client.get_collections()
        elif version == "prod_remote":
            self.client = QdrantClient(
                url=env.PROD_QDRANT_URL, port=443, https=True, timeout=30, api_key=env.PROD_QDRANT_API_KEY
            )
            _ = self.client.get_collections()
        else:
            raise ValueError("Version must be either 'memory' or 'disk' or 'remote'")

    def as_llama_vector_store(self, collection_name) -> QdrantVectorStore:
        return QdrantVectorStore(client=self.client, collection_name=collection_name, max_retries=10)

    def create_collection(self, collection_name, vector_size, enable_sparse: bool = False) -> None:
        """Create a Qdrant collection with optional sparse vector support.
        
        Args:
            collection_name: Name of the collection
            vector_size: Size of dense vectors
            enable_sparse: If True, enables sparse vectors for hybrid search
        """
        try:
            _ = self.client.get_collection(collection_name=collection_name)
            print(f"Collection '{collection_name}' already exists.")
        except UnexpectedResponse as e:
            if enable_sparse:
                # Create collection with both dense and sparse vectors for hybrid retrieval
                _ = self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config={
                        "dense": VectorParams(size=vector_size, distance=Distance.COSINE),
                    },
                    sparse_vectors_config={
                        "sparse": SparseVectorParams(),
                    },
                )
                print(f"Created hybrid collection '{collection_name}' with dense (size={vector_size}) and sparse vectors.")
            else:
                # Legacy: Dense-only collection
                _ = self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.DOT),
                )
                print(f"Created dense-only collection '{collection_name}' with size={vector_size}.")

    def upsert(self, collection_name, points: list[dict]) -> None:
        """Upsert points into Qdrant collection.
        
        Supports both dense-only and hybrid (dense + sparse) vectors.
        
        Args:
            collection_name: Target collection name
            points: List of point dicts with 'id', 'vector', and 'payload'
                   'vector' can be:
                   - list[float] for dense-only collections
                   - dict with 'dense' and 'sparse' keys for hybrid collections
        """
        qdrant_points = [PointStruct(**point) for point in points]
        try:
            operation_info = self.client.upsert(
                collection_name=collection_name,
                wait=True,
                points=qdrant_points,
            )
        except ResponseHandlingException as e:
            # Z.B. httpx.RemoteProtocolError: "Server disconnected without sending a response".
            # Nur diesen Batch überspringen und weitermachen, statt den gesamten Lauf abzubrechen.
            print(
                f"Qdrant upsert failed for batch of {len(points)} points into '{collection_name}': {e}"
            )
            return

        print(f"Upserted {len(points)} points into '{collection_name}': {operation_info}")

    def search(self, collection_name, query_vector, query_filter=None, with_payload=True, limit=10) -> list[dict]:
        """Search in Qdrant collection.
        
        Supports both dense-only and hybrid (dense + sparse) search.
        
        Args:
            collection_name: Collection to search in
            query_vector: Query vector (list[float] for dense-only, dict for hybrid)
            query_filter: Optional Qdrant filter
            with_payload: Include payload in results
            limit: Maximum number of results
            
        Returns:
            List of search results
        """
        search_result = self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            query_filter=query_filter,
            with_payload=with_payload,
            limit=limit,
        )
        return search_result

    def get_course_module_records(self, collection_name):
        all_records = []

        next_page_offset = "first"
        offset = None

        while next_page_offset:
            if next_page_offset != "first":
                offset = next_page_offset

            try:
                records = self.client.scroll(
                    collection_name=collection_name,
                with_payload=True,
                    with_vectors=False,
                    limit=10,
                    offset=offset,
                )
            
            except ResponseHandlingException as e:
                print(f"Qdrant ResponseHandlingException: {e}")
                return [], []
            except Exception as e:
                print(f"Qdrant unknown Exception: {e}")
                return [], []

            next_page_offset = records[1]

            all_records.extend(records[0])

        courses_records = sorted(
            [
                record
                for record in all_records
                if "module_id" not in record.payload
                and "course_id" in record.payload
                and isinstance(record.payload["course_id"], int)
            ],
            key=lambda x: x.payload["course_id"],
        )
        modules_records = sorted(
            [record for record in all_records if "module_id" in record.payload], key=lambda x: x.payload["module_id"]
        )

        return courses_records, modules_records

    def check_if_course_exists(self, course_id: int) -> bool:
        """Check if a course exists in the database."""

        scroll_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="course_id",
                    match=models.MatchValue(value=course_id),
                ),
            ],
        )
        return bool(self.query_with_filter("web_assistant", scroll_filter))

    def check_if_module_exists(self, module_id: int) -> bool:
        """Check if a module exists in the database."""

        scroll_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="course_id",
                    match=models.MatchValue(value=module_id),
                ),
            ],
        )
        return bool(self.query_with_filter("web_assistant", scroll_filter))

    def query_with_filter(self, collection_name, scroll_filter) -> List:
        records = self.client.scroll(
            collection_name=collection_name,
            scroll_filter=scroll_filter,
            with_payload=True,
            with_vectors=False,
            limit=10,
        )

        return records


if __name__ == "__main__":
    test_connection = VectorDBQdrant(version="disk")  # For local testing only
