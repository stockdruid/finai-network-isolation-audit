from functools import lru_cache

from rag.chroma_store import get_collection
from rag.embeddings import embed

# 이 거리(L2)보다 먼 문서는 관련 없는 것으로 보고 컨텍스트에서 제외.
# (실측: 관련 상품/고객 매치 ~95~117, 엉뚱한/모호한 질문 ~187+)
MAX_DISTANCE = 150.0

# 고객 개인정보 조회 의도로 볼 키워드. 이 경우에만 persona 문서를 검색한다.
CUSTOMER_LOOKUP_KEYWORDS = ["고객", "회원", "가입자", "개인정보", "이 사람", "저 사람"]


@lru_cache(maxsize=1)
def _persona_names() -> tuple[str, ...]:
    """시드된 고객 persona 이름 목록 (캐시). 질문에 이름이 나오면 조회 의도로 본다."""
    try:
        g = get_collection().get(where={"source": "customer_persona"})
        return tuple(
            m.get("customer_name") for m in g["metadatas"] if m.get("customer_name")
        )
    except Exception:
        return ()


def is_customer_lookup(query: str) -> bool:
    """질문이 특정 고객의 개인정보를 명시적으로 조회하는 의도인지 판별.

    True일 때만 persona(고객 PII)를 검색한다. 일반 상품/금융 질문에는 남의
    개인정보가 섞이지 않도록 하기 위함. (EV-002는 이 명시적 조회에서만 발동)
    """
    if any(kw in query for kw in CUSTOMER_LOOKUP_KEYWORDS):
        return True
    return any(name in query for name in _persona_names())


def retrieve(
    query: str, top_k: int = 3, max_distance: float = MAX_DISTANCE
) -> list[tuple[str, dict]]:
    """질문과 유사한 상위 K개 문서를 (document, metadata)로 반환.

    - 관련도가 낮은(거리가 먼) 문서는 제외.
    - 명시적 고객 조회가 아니면 고객 persona(PII)는 검색 대상에서 제외한다.
    """
    collection = get_collection()
    q_emb = embed(query)

    # 고객 조회가 아니면 persona 제외 → 일반 질문에 남의 개인정보가 안 섞임
    where = None if is_customer_lookup(query) else {"source": {"$ne": "customer_persona"}}

    result = collection.query(
        query_embeddings=[q_emb],
        n_results=top_k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    dists = result.get("distances", [[]])[0]

    hits: list[tuple[str, dict]] = []
    for doc, meta, dist in zip(docs, metas, dists, strict=False):
        if dist <= max_distance:
            hits.append((doc, meta))
    return hits
