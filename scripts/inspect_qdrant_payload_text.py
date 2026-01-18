"""Small helper to diagnose Unicode issues in Qdrant payload text.

Usage (PowerShell/cmd):
  python scripts/inspect_qdrant_payload_text.py --id 00baf11b-2e67-4c27-a436-c39624cf0abc

Notes:
  - Uses DEV_QDRANT_URL/DEV_QDRANT_API_KEY (preferred) or QDRANT_URL/QDRANT_API_KEY.
  - Prints combining marks counts so we can detect decomposed umlauts (e.g., u + U+0308).
"""

from __future__ import annotations

import argparse
import os
import unicodedata

from qdrant_client import QdrantClient


def _combining_marks(text: str):
    return [
        (i, ch, hex(ord(ch)), unicodedata.name(ch, ""))
        for i, ch in enumerate(text)
        if unicodedata.combining(ch)
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="Point id (uuid)")
    ap.add_argument("--collection", default="web_assistant_hybrid")
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
    pts = client.retrieve(
        collection_name=args.collection,
        ids=[args.id],
        with_payload=True,
        with_vectors=False,
    )
    if not pts:
        print("Point not found")
        return 2

    payload = pts[0].payload or {}
    text = payload.get("text") or ""
    print("id:", args.id)
    print("collection:", args.collection)
    print("text_preview:", text[:200])
    print("repr_preview:", repr(text[:200]))

    comb = _combining_marks(text)
    print("combining_marks_count:", len(comb))
    print("first_combining_marks:", comb[:20])

    # Also show what NFC would look like, without mutating stored data.
    nfc = unicodedata.normalize("NFC", text)
    print("nfc_repr_preview:", repr(nfc[:200]))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

