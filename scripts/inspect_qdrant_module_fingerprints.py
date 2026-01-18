"""Inspect stored Moodle ModuleFingerprint points in Qdrant.

Example:
  python scripts/inspect_qdrant_module_fingerprints.py --course-id 16 --limit 20
"""

from __future__ import annotations

import argparse
import os

from qdrant_client import QdrantClient
from qdrant_client.http import models


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--course-id", type=int, required=True)
    ap.add_argument("--collection", default="web_assistant_hybrid")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument(
        "--url",
        default=(
            os.getenv("DEV_QDRANT_URL")
            or os.getenv("QDRANT_URL")
            or "https://qdrant-app.wittywater-56b7efb4.germanywestcentral.azurecontainerapps.io"
        ),
    )
    ap.add_argument(
        "--api-key",
        default=(os.getenv("DEV_QDRANT_API_KEY") or os.getenv("QDRANT_API_KEY")),
    )
    args = ap.parse_args()

    client = QdrantClient(url=args.url, port=443, https=True, api_key=args.api_key, timeout=60)

    flt = models.Filter(
        must=[
            models.FieldCondition(key="source", match=models.MatchValue(value="Moodle")),
            models.FieldCondition(key="type", match=models.MatchValue(value="ModuleFingerprint")),
            models.FieldCondition(key="course_id", match=models.MatchValue(value=args.course_id)),
        ]
    )

    points, _ = client.scroll(
        collection_name=args.collection,
        scroll_filter=flt,
        with_payload=True,
        with_vectors=False,
        limit=args.limit,
    )
    points = points or []

    print(f"course_id={args.course_id} module_fingerprint_points={len(points)}")
    for p in sorted(points, key=lambda x: int(x.payload.get("module_id", 0) or 0)):
        payload = p.payload or {}
        print(
            {
                "id": str(p.id),
                "module_id": payload.get("module_id"),
                "module_fingerprint": payload.get("module_fingerprint"),
                "module_fingerprint_version": payload.get("module_fingerprint_version"),
                "url": payload.get("url"),
            }
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

