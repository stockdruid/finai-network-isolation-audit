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


def _get(path: str, params: dict | None = None) -> Any:
    try:
        r = httpx.get(f"{API_BASE_URL}{path}", params=params, timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as exc:
        st.error(f"API 호출 실패 ({path}): {exc}")
        return None


def _post(path: str, json: dict | None = None) -> Any:
    try:
        r = httpx.post(f"{API_BASE_URL}{path}", json=json or {}, timeout=DEFAULT_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as exc:
        st.error(f"API 호출 실패 ({path}): {exc}")
        return None


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30)
def fetch_logs(
    mode: str | None = None,
    since: int = 0,
    limit: int = 100,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"since": since, "limit": limit}
    if mode:
        params["mode"] = mode
    return _get("/logs", params) or []


def fetch_log_detail(log_id: int) -> dict | None:
    return _get(f"/logs/{log_id}")


# ---------------------------------------------------------------------------
# Diagnosis
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30)
def fetch_diagnoses(
    severity: str | None = None,
    source_log_id: int | None = None,
    since: int = 0,
    limit: int = 100,
) -> list[dict]:
    params: dict[str, Any] = {"since": since, "limit": limit}
    if severity:
        params["severity"] = severity
    if source_log_id is not None:
        params["source_log_id"] = source_log_id
    return _get("/diagnosis", params) or []


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def fetch_policies(category: str | None = None) -> list[dict]:
    params = {}
    if category:
        params["category"] = category
    return _get("/policies", params) or []


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30)
def fetch_stats_overview() -> dict:
    return _get("/stats/overview") or {}


@st.cache_data(ttl=30)
def fetch_stats_violations() -> list[dict]:
    return _get("/stats/violations") or []


@st.cache_data(ttl=30)
def fetch_stats_severity() -> list[dict]:
    return _get("/stats/severity") or []


@st.cache_data(ttl=30)
def fetch_stats_timeline(days: int = 30) -> list[dict]:
    return _get("/stats/timeline", {"days": days}) or []


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def generate_report(scan_id: str | None = None) -> dict | None:
    return _post("/reports/generate", {"scan_id": scan_id} if scan_id else {})


# ---------------------------------------------------------------------------
# Health / sidebar
# ---------------------------------------------------------------------------

def health_ok() -> bool:
    try:
        r = httpx.get(f"{API_BASE_URL}/health", timeout=2.0)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


def sidebar_status() -> None:
    with st.sidebar:
        st.divider()
        if health_ok():
            st.success(f"API: {API_BASE_URL}")
        else:
            st.error(f"API 연결 실패: {API_BASE_URL}")


def sidebar_filters(
    *,
    show_mode: bool = False,
    show_severity: bool = False,
    show_period: bool = False,
    show_limit: bool = False,
) -> dict[str, Any]:
    """공용 사이드바 필터. 필요한 필터만 켜서 사용."""
    filters: dict[str, Any] = {}
    with st.sidebar:
        st.subheader("🔎 필터")

        if show_mode:
            mode = st.selectbox(
                "호출 모드",
                options=["전체", "internal", "external"],
                index=0,
                key="filter_mode",
            )
            filters["mode"] = None if mode == "전체" else mode

        if show_severity:
            severity = st.selectbox(
                "심각도",
                options=["전체", "critical", "high", "medium", "low", "info"],
                index=0,
                key="filter_severity",
            )
            filters["severity"] = None if severity == "전체" else severity

        if show_period:
            period = st.slider(
                "기간 (일)", min_value=7, max_value=90, value=30, step=7,
                key="filter_period",
            )
            filters["period"] = period

        if show_limit:
            limit = st.slider(
                "표시 수", min_value=10, max_value=1000, value=100, step=10,
                key="filter_limit",
            )
            filters["limit"] = limit

    return filters
