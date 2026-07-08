from rag.chroma_store import get_collection
from rag.embeddings import embed_batch


def ingest(items: list[dict]) -> int:
    """상품 문서를 Chroma에 일괄 적재.

    items: [{id, document, metadata}, ...]
    """
    if not items:
        return 0

    collection = get_collection()
    ids = [it["id"] for it in items]
    docs = [it["document"] for it in items]
    metas = [it["metadata"] for it in items]
    embs = embed_batch(docs)

    # upsert: 같은 id면 덮어쓰기
    collection.upsert(ids=ids, documents=docs, embeddings=embs, metadatas=metas)
    return len(items)
