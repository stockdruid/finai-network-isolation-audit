"""MVP12 Detector 카탈로그 — 자동화 명세와 우선순위 조망.

원천: 시트 `18_MVP12_자동화명세` (12건 Detector).
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from pages._api import fetch_detectors, sidebar_status

st.set_page_config(page_title="Detector 카탈로그", page_icon="🎯", layout="wide")
st.title("🎯 MVP12 Detector 카탈로그")
st.caption("자동화 탐지기 명세 — 챗봇/시스템/데이터 영역 12종")

sidebar_status()

# ---------------------------------------------------------------------------
# 사이드바 필터
# ---------------------------------------------------------------------------
with st.sidebar:
    st.subheader("🔎 필터")
    area = st.selectbox("영역", ["전체", "챗봇", "시스템", "데이터"], index=0)
    prio = st.selectbox("우선순위", ["전체", "P1", "P2", "P3"], index=0)
    auto = st.selectbox("자동화", ["전체", "AUTO", "SEMI_AUTO", "MANUAL"], index=0)

detectors = fetch_detectors(
    area=None if area == "전체" else area,
    priority=None if prio == "전체" else prio,
    automation=None if auto == "전체" else auto,
)

if not detectors:
    st.warning("Detector 데이터가 없다. `scripts/import_compliance_mappings.py` 실행 필요.")
    st.stop()

df = pd.DataFrame(detectors)

# ---------------------------------------------------------------------------
# KPI
# ---------------------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("총 Detector", f"{len(df)}")
c2.metric("P1", int((df["priority"] == "P1").sum()))
c3.metric("AUTO", int((df["automation"] == "AUTO").sum()))
c4.metric("SEMI_AUTO", int((df["automation"] == "SEMI_AUTO").sum()))

st.divider()

# ---------------------------------------------------------------------------
# 차트 2종
# ---------------------------------------------------------------------------
col1, col2 = st.columns(2)
with col1:
    area_agg = df.groupby("area").size().reset_index(name="count")
    fig_a = px.bar(
        area_agg,
        x="area",
        y="count",
        color="area",
        title="영역별 Detector",
    )
    st.plotly_chart(fig_a, use_container_width=True)

with col2:
    if "automation" in df:
        auto_agg = df.groupby("automation").size().reset_index(name="count")
        fig_b = px.pie(
            auto_agg,
            names="automation",
            values="count",
            title="자동화 수준 분포",
        )
        st.plotly_chart(fig_b, use_container_width=True)

# ---------------------------------------------------------------------------
# 상세 카드
# ---------------------------------------------------------------------------
st.subheader("📖 Detector 상세")
for row in detectors:
    with st.expander(
        f"**[{row.get('priority') or '?'}] {row['detector_id']}** — {row.get('scenario') or ''}",
        expanded=False,
    ):
        cA, cB = st.columns([2, 1])
        with cA:
            st.markdown(f"**영역**: {row.get('area','')}  |  **자동화**: `{row.get('automation','')}`")
            st.markdown(f"**Finding ID**: `{row.get('finding_id') or '-'}`")
            st.markdown(f"**점검대상**: {row.get('target') or '-'}")
            st.markdown(f"**주요 증적**: {row.get('evidence') or '-'}")
            st.markdown(f"**적합조건** ✅: {row.get('pass_criteria') or '-'}")
            st.markdown(f"**부적합조건** ❌: {row.get('fail_criteria') or '-'}")
            st.markdown(f"**가드레일·개선조치**: {row.get('guardrail') or '-'}")
        with cB:
            st.markdown(f"**상태**: `{row.get('status','proposed')}`")
            st.markdown(f"**개발담당**: {row.get('dev_owner') or '-'}")
            st.markdown(f"**정책담당**: {row.get('policy_owner') or '-'}")
            refs = row.get("reference_standards") or []
            if refs:
                st.markdown("**참조 기준**:")
                for r in refs:
                    st.markdown(f"- {r}")

st.divider()
st.subheader("📋 원본 테이블")
st.dataframe(df, use_container_width=True, height=400)
