# finai-compliance — FastAPI + Streamlit 공용 이미지
#
# 같은 이미지로 두 서비스(api, ui) 실행. compose에서 CMD로 분기.
# 이미지 크기 최적화보다 재현성 우선 (파이널 프로젝트 발표 안정성).
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONIOENCODING=utf-8

# 시스템 패키지 (asyncpg 빌드, healthcheck용 curl, 한글 로케일)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libpq-dev \
        gcc \
        locales \
    && locale-gen ko_KR.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

ENV LANG=ko_KR.UTF-8 LC_ALL=ko_KR.UTF-8

WORKDIR /app

# 의존성 레이어 캐싱을 위해 requirements 먼저 복사
COPY requirements.txt requirements-dev.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# 소스 복사 (dockerignore로 .venv, __pycache__ 제외)
COPY . .

EXPOSE 8000 8501

# 기본은 FastAPI. compose에서 UI 서비스는 command로 오버라이드.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
