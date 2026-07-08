from functools import lru_cache

from sentence_transformers import SentenceTransformer

from core.config import settings


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    # 최초 호출 시 모델 다운로드 (약 500MB), 이후 캐시 사용
    return SentenceTransformer(settings.embedding_model)


def embed(text: str) -> list[float]:
    model = get_model()
    return model.encode(text).tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    model = get_model()
    return model.encode(texts).tolist()
