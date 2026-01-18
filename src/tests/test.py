import os
import unicodedata
from qdrant_client import QdrantClient

QDRANT_URL = os.getenv("DEV_QDRANT_URL") or os.getenv("QDRANT_URL") or "https://qdrant-app.wittywater-56b7efb4.germanywestcentral.azurecontainerapps.io"
API_KEY = "UAviTSirwdmm5I2hyaiBuUpI53Y3DjVgI1jXFegjqhG62pF580SkiQqFdMkmQN1Q"
COLLECTION = "web_assistant_hybrid"
POINT_ID = "00baf11b-2e67-4c27-a436-c39624cf0abc"

client = QdrantClient(url=QDRANT_URL, port=443, https=True, api_key=API_KEY, timeout=60)
pts = client.retrieve(collection_name=COLLECTION, ids=[POINT_ID], with_payload=True, with_vectors=False)

if not pts:
    raise SystemExit("Point not found")

text = pts[0].payload.get("text", "")
print("raw preview:", text[:200])
print("repr:", repr(text[:200]))

# show any combining marks (e.g., U+0308)
comb = [(i, ch, hex(ord(ch)), unicodedata.name(ch, "")) for i, ch in enumerate(text) if unicodedata.combining(ch)]
print("combining_marks_count:", len(comb))
print("first_combining_marks:", comb[:20])

# Compare NFC vs NFKD
nfc = unicodedata.normalize("NFC", text)
nfkd = unicodedata.normalize("NFKD", text)
print("NFC repr snippet:", repr(nfc[:200]))
print("NFKD repr snippet:", repr(nfkd[:200]))
