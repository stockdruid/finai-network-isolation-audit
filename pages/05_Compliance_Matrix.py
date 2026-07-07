"""컴플라이언스 매핑 매트릭스 — 공통통제 × 원천기준 교차표.

원천: 시트 `22_프로젝트적용_통합` (269건 요구사항).
"""
from __future__ import annotations

from collections import defaultdict

import pandas as pd
import plotly.express as px
import streamlit as st

from pages._api import fetch_controls, fetch_matrix, fetch_requirements, sidebar_status

st.set_page_config(page_title="컴플라이언스 매트릭스", page_icon="🧩", layout="wide")
st.title("🧩 컴플라이언스 매핑 매트릭스")
st.caption("공통통제(GOV/DATA/MODEL/OPS/INFRA) × 원천기준 매핑 관계")

sidebar_status()

# ---------------------------------------------------------------------------
# 데이터 로드
# ---------------------------------------------------------------------------
matrix = fetch_matrix()
controls = fetch_controls()
requirements = fetch_requirements(limit=1000)

if not matrix or not controls:
    st.warning("매핑 데이터가 없다. `scripts/import_compliance_mappings.py` 실행 필요.")
    st.stop()

df_matrix = pd.DataFrame(matrix)
df_controls = pd.DataFrame(controls)
df_reqs = pd.DataFrame(requirements)

# ---------------------------------------------------------------------------
# KPI 카드
# ---------------------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("공통통제", f"{len(df_controls)}")
c2.metric("요구사항", f"{len(df_reqs)}")
c3.metric("원천기준", f"{df_matrix['source_standard'].nunique()}")
c4.metric("매핑 관계", f"{int(df_matrix['count'].sum())}")

st.divider()

# ---------------------------------------------------------------------------
# 히트맵 — 원천기준 × 공통통제
# ---------------------------------------------------------------------------
st.subheader("🔥 매핑 히트맵")
pivot = df_matrix.pivot_table(
    index="source_standard",
    columns="control_id",
    values="count",
    fill_value=0,
    aggfunc="sum",
)
fig = px.imshow(
    pivot,
    color_continuous_scale="Reds",
    aspect="auto",
    labels={"x": "공통통제 ID", "y": "원천기준", "color": "매핑 수"},
)
fig.update_layout(height=500)
st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# 도메인별 분포
# ---------------------------------------------------------------------------
st.subheader("🌐 도메인별 통제 분포")

# control_id → domain 매핑
domain_map = dict(zip(df_controls["control_id"], df_controls["domain"]))
df_matrix["domain"] = df_matrix["control_id"].map(domain_map).fillna("미분류")

col1, col2 = st.columns(2)
with col1:
    domain_agg = (
        df_matrix.groupby("domain")["count"]
        .sum()
        .reset_index()
        .sort_values("count", ascending=False)
    )
    fig_d = px.pie(domain_agg, names="domain", values="count", title="도메인별 매핑 비중")
    st.plotly_chart(fig_d, use_container_width=True)

with col2:
    src_agg = (
        df_matrix.groupby("source_standard")["count"]
        .sum()
        .reset_index()
        .sort_values("count", ascending=True)
    )
    fig_s = px.bar(
        src_agg,
        x="count",
        y="source_standard",
        orientation="h",
        title="원천기준별 매핑 수",
    )
    fig_s.update_layout(height=400)
    st.plotly_chart(fig_s, use_container_width=True)

# ---------------------------------------------------------------------------
# 원본 매트릭스 테이블
# ---------------------------------------------------------------------------
st.subheader("📋 원본 매핑 데이터")
tab1, tab2, tab3 = st.tabs(["공통통제", "요구사항", "히트맵 원본"])

with tab1:
    st.dataframe(df_controls, use_container_width=True, height=400)

with tab2:
    if not df_reqs.empty:
        show_cols = [
            "source_standard", "requirement_id", "name", "control_id",
            "relationship_type", "detector_id", "priority", "verdict",
        ]
        st.dataframe(df_reqs[show_cols], use_container_width=True, height=500)

with tab3:
    st.dataframe(df_matrix, use_container_width=True, height=400)
