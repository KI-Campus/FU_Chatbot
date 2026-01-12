import logging
from datetime import datetime
from typing import List
import uuid

from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import TextNode
from qdrant_client.http import models
from tqdm import tqdm

from src.env import env
from src.llm.objects.LLMs import LLM
from src.vectordb.sparse_encoder import BM25SparseEncoder
from src.loaders.drupal import Drupal
from src.loaders.moochup import Moochup
from src.loaders.moodle import Moodle
from src.vectordb.qdrant import VectorDBQdrant

DEFAULT_COLLECTION = "web_assistant_hybrid"
SNAPSHOTS_TO_KEEP = 3


# A full run takes about 2,5 hours (2025-02-11)
class Fetch_Data:
    def sanity_check(self):
        # Check if URLs are missing in metadata,
        # every point needs a non-empty url field in the metadata
        query_filter = models.Filter(must=[models.IsEmptyCondition(is_empty=models.PayloadField(key="url"))])

        if self.dev_vector_store.query_with_filter(DEFAULT_COLLECTION, query_filter) != ([], None):
            self.logger.error("Missing URLs in Metadata, linking to content not possible in all cases")

    def __init__(self):
        self.DATA_PATH = "./data"
        self.embedder = LLM().get_embedder()
        self.sparse_encoder = BM25SparseEncoder()  # NEW: Sparse encoder for hybrid retrieval
        self.logger = logging.getLogger("loader")
        self.logger.propagate = False
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "{asctime} - {levelname:<8} - {message}",
                style="{",
                datefmt="%d-%b-%y %H:%M:%S",
            )
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        self.logger.setLevel(logging.DEBUG if env.DEBUG_MODE else logging.INFO)
        self.dev_vector_store = VectorDBQdrant(version="dev_remote")
        self.prod_vector_store = VectorDBQdrant(version="prod_remote")

        self.logger.info("Starting data extraction...")

    def extract(
        self,
    ):
        self.logger.info("Create Snapshot of previous data collection...")
        if self.dev_vector_store.client.collection_exists(DEFAULT_COLLECTION):
            new_snapshot = self.dev_vector_store.client.create_snapshot(collection_name=DEFAULT_COLLECTION, wait=False)

            # There will likely be one additional snapshot because the snapshot created in the previous step has not yet been added to the list.
            all_snapshots: List[models.SnapshotDescription] = self.dev_vector_store.client.list_snapshots(
                collection_name=DEFAULT_COLLECTION
            )
            sorted_snapshots = self.sort_snapshots_by_creation_time(all_snapshots)
            if len(all_snapshots) >= SNAPSHOTS_TO_KEEP:
                for snapshot in sorted_snapshots[SNAPSHOTS_TO_KEEP:]:
                    self.logger.debug(f"Deleting {snapshot.name}")
                    self.dev_vector_store.client.delete_snapshot(
                        collection_name=DEFAULT_COLLECTION, snapshot_name=snapshot.name
                    )

        self.logger.info("Loading Moodle data from Moochup API...")
        moodle_moochup_courses = Moochup(env.DATA_SOURCE_MOOCHUP_MOODLE_URL).get_course_documents()
        self.logger.info("Finished loading data from Moochup API.")
        self.logger.info("Loading Moodle data from Moodle API...")
        moodle_courses = Moodle().extract()
        self.logger.info("Finished loading data from Moodle API.")
        self.logger.info("Loading Drupal data from Drupal API...")
        drupal_content = Drupal(
            base_url=env.DRUPAL_URL,
            username=env.DRUPAL_USERNAME,
            client_id=env.DRUPAL_CLIENT_ID,
            client_secret=env.DRUPAL_CLIENT_SECRET,
            grant_type=env.DRUPAL_GRANT_TYPE,
        ).extract()

        all_docs = moodle_moochup_courses + moodle_courses + drupal_content

        def chunk_list(lst, chunk_size):
            """Yield successive chunk_size-sized chunks from lst."""
            for i in range(0, len(lst), chunk_size):
                yield lst[i : i + chunk_size]

        # Qdrant payload size limit: 32MB, we target 30MB to be safe
        MAX_BATCH_SIZE_BYTES = 30 * 1024 * 1024  # 30 MB
        
        def calculate_point_size(point: dict) -> int:
            """Calculate the exact JSON payload size of a single point in bytes."""
            import json
            return len(json.dumps(point, default=str).encode('utf-8'))
        
        def batch_by_size(points: list, max_size_bytes: int):
            """Yield batches of points that fit within the size limit."""
            current_batch = []
            current_size = 0
            
            for point in points:
                point_size = calculate_point_size(point)
                
                # If a single point exceeds the limit, log warning and send it alone
                if point_size > max_size_bytes:
                    if current_batch:
                        yield current_batch
                        current_batch = []
                        current_size = 0
                    yield [point]  # Send oversized point alone
                    continue
                
                # Check if adding this point would exceed the limit
                if current_size + point_size > max_size_bytes:
                    yield current_batch
                    current_batch = [point]
                    current_size = point_size
                else:
                    current_batch.append(point)
                    current_size += point_size
            
            # Don't forget the last batch
            if current_batch:
                yield current_batch

        chunk_size = 100  # For document processing, not Qdrant batching

        self.logger.debug("Deleting old collection from Qdrant...")
        self.dev_vector_store.client.delete_collection(collection_name=DEFAULT_COLLECTION)
        
        # Detect embedding dimension dynamically
        sample_embedding = self.embedder.get_text_embedding("test")
        embedding_dim = len(sample_embedding)
        self.logger.info(f"Detected embedding dimension: {embedding_dim}")
        
        # Create new collection with hybrid vector support
        self.logger.info(f"Creating hybrid collection '{DEFAULT_COLLECTION}' with dense + sparse vectors...")
        self.dev_vector_store.create_collection(
            collection_name=DEFAULT_COLLECTION,
            vector_size=embedding_dim,
            enable_sparse=True
        )

        self.logger.info(f"Processing and loading {len(all_docs)} documents with hybrid vectors...")
        
        # Manual processing for hybrid vectors (replacing LlamaIndex pipeline)
        splitter = SentenceSplitter(chunk_size=256, chunk_overlap=16)
        
        total_points_upserted = 0
        for batch in tqdm(chunk_list(all_docs, chunk_size), desc="Processing batches"):
            # Step 1: Chunk documents into nodes
            nodes = splitter.get_nodes_from_documents(batch)
            
            # Step 2: Generate dense embeddings (batch)
            texts_to_embed = [node.get_content() for node in nodes]
            dense_embeddings = self.embedder.get_text_embedding_batch(texts_to_embed)
            
            # Step 3: Prepare hybrid points with both dense and sparse vectors
            hybrid_points = []
            for node, dense_vec in zip(nodes, dense_embeddings):
                text = node.get_content()
                sparse_vec = self.sparse_encoder.encode(text)
                
                point = {
                    "id": node.node_id or str(uuid.uuid4()),
                    "vector": {
                        "dense": dense_vec,
                        "sparse": sparse_vec,
                    },
                    "payload": {
                        "text": text,
                        **node.metadata,
                    }
                }
                hybrid_points.append(point)
            
            # Step 4: Upsert to Qdrant in size-limited batches
            for size_batch in batch_by_size(hybrid_points, MAX_BATCH_SIZE_BYTES):
                batch_size_mb = sum(calculate_point_size(p) for p in size_batch) / (1024 * 1024)
                self.logger.debug(f"Upserting batch of {len(size_batch)} points (~{batch_size_mb:.1f} MB)")
                self.dev_vector_store.upsert(DEFAULT_COLLECTION, size_batch)
                total_points_upserted += len(size_batch)
        
        self.logger.info(f"Total points upserted: {total_points_upserted}")

        self.logger.info("Finished loading Docs into Dev Qdrant.")
        self.logger.info(f"Migrate dev collection '{DEFAULT_COLLECTION}' to prod collection")
        self.dev_vector_store.client.migrate(
            self.prod_vector_store.client, [DEFAULT_COLLECTION], recreate_on_collision=True
          )
        self.logger.info("Migration successful")

        self.sanity_check()

    def sort_snapshots_by_creation_time(
        self, snapshots: List[models.SnapshotDescription]
    ) -> List[models.SnapshotDescription]:
        return sorted(
            snapshots,
            key=lambda snapshot: datetime.fromisoformat(snapshot.creation_time)
            if snapshot.creation_time
            else datetime.min,
            reverse=True,
        )


if __name__ == "__main__":
    Fetch_Data().extract()
