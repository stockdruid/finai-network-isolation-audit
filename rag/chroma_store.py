from functools import lru_cache

import chromadb

from core.config import settings

COLLECTION_NAME = "products"


@lru_cache(maxsize=1)
def get_client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=settings.chroma_path)


def get_collection():
    # collection은 매번 가져오는 게 안전 (server-side state 변경 가능성)
    return get_client().get_or_create_collection(COLLECTION_NAME)
