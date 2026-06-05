"""Streamlit 대시보드 공용 API 클라이언트 — FastAPI(localhost:8000)와 HTTP 통신.

Streamlit은 pages/ 아래 `_` 로 시작하는 파일은 페이지로 등록하지 않으므로
공용 유틸을 여기에 둔다.
"""
from __future__ import annotations

import os
from typing import Any

import httpx
import streamlit as st

API_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")
DEFAULT_TIMEOUT = 5.0


@st.cache_data(ttl=30)
def fetch_logs(
    mode: str | None = None,
    since: int = 0,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """GET /logs 폴링. 30초 캐시."""
    params: dict[str, Any] = {"since": since, "limit": limit}
    if mode:
        params["mode"] = mode
    try:
        r = httpx.get(f"{API_BASE_URL}/logs", params=params, timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as exc:
        st.error(f"FastAPI 호출 실패: {exc}")
        return []


def health_ok() -> bool:
    try:
        r = httpx.get(f"{API_BASE_URL}/health", timeout=2.0)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


def sidebar_status() -> None:
    """모든 페이지 사이드바 하단에 API 상태 표시."""
    with st.sidebar:
        st.divider()
        if health_ok():
            st.success(f"API: {API_BASE_URL}")
        else:
            st.error(f"API 연결 실패: {API_BASE_URL}")
