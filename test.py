from qdrant_client.http.exceptions import UnexpectedResponse

from src.env import env
from src.vectordb.qdrant import VectorDBQdrant

COLLECTION = "web_assistant_hybrid"


def _mask_key(key: str) -> str:
    if not key:
        return "<leer>"
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key}"


def check(version: str) -> None:
    # API-Key laut EnvHelper ausgeben (maskiert)
    try:
        if version == "dev_remote":
            api_key = env.DEV_QDRANT_API_KEY
        elif version == "prod_remote":
            api_key = env.PROD_QDRANT_API_KEY
        else:
            api_key = ""
        print(f"[{version}] Verwendeter API-Key: {_mask_key(api_key)}")
    except AttributeError as e:
        print(f"[{version}] Kein API-Key gesetzt: {e}")

    try:
        db = VectorDBQdrant(version=version)
        info = db.client.get_collection(collection_name=COLLECTION)
        print(f"[{version}] Collection '{COLLECTION}' EXISTIERT.")
        print(f"[{version}] Details: {info}")
    except UnexpectedResponse:
        print(f"[{version}] Collection '{COLLECTION}' existiert NICHT.")
    except Exception as e:
        print(f"[{version}] Fehler beim Prüfen: {e}")


if __name__ == "__main__":
    check("dev_remote")
    check("prod_remote")