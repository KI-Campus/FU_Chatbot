from src.vectordb.qdrant import VectorDBQdrant
from qdrant_client.http.models import Filter, FieldCondition, MatchValue

COLLECTION_NAME = "web_assistant_hybrid"
TARGET_COURSE_ID = None

# Verbindung zu Qdrant
db = VectorDBQdrant()

# Filter definieren
course_filter = Filter(
    must=[
        FieldCondition(
            key="course_id",
            match=MatchValue(value=TARGET_COURSE_ID)
            #key="source",
            #match=MatchValue(value="Drupal")
        )
    ]
)

# Scroll-Query ausführen (lädt alle passenden Punkte seitenweise)
all_points = []
next_page_offset = None

while True:
    points, next_page_offset = db.client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=course_filter,
        limit=200,
        with_payload=True,#with_payload=["module_id", "fullname", "url"],
        with_vectors=False,
        offset=next_page_offset
    )

    all_points.extend(points)

    if next_page_offset is None:
        break

# Ausgabe
#print(f"Gefundene Chunks: {len(all_points)}\n")

for p in all_points:
    print("ID:", p.id)
    print("Payload:", p.payload)
    print("-" * 40)