"""금융권 ISMS-P 인증기준 페이지.

- 48 인증기준 선정 요약 + 대분류/분야별 필터
- 191 세부 점검항목 (법령·제재 매핑) 브라우저
- 판정 현황 파이차트 (미평가/적합/부적합 등)

원천: 정책팀 자료 `금융권_적합_ISMS-P_법령_매핑.xlsx` (2026-07-07).
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from pages._api import (
    fetch_isms_p_category_summary,
    fetch_isms_p_checklist,
    fetch_isms_p_criteria,
    fetch_isms_p_verdict_summary,
    sidebar_status,
)

st.set_page_config(page_title="ISMS-P 점검표", page_icon="📋", layout="wide")
st.title("📋 금융권 ISMS-P 인증기준")
st.caption("48 인증기준 + 191 세부 점검항목 + 법령·제재 매핑 (금융보안원 선정 범위)")

sidebar_status()

criteria = fetch_isms_p_criteria()
verdict_summary = fetch_isms_p_verdict_summary()
category_summary = fetch_isms_p_category_summary()

if not criteria:
    st.warning("데이터가 없다. `scripts/import_isms_p.py` 실행 필요.")
    st.stop()

df_criteria = pd.DataFrame(criteria)
df_verdict = pd.DataFrame(verdict_summary) if verdict_summary else pd.DataFrame()
df_category = pd.DataFrame(category_summary) if category_summary else pd.DataFrame()

# ---------------------------------------------------------------------------
# KPI 카드
# ---------------------------------------------------------------------------
k1, k2, k3, k4 = st.columns(4)
k1.metric("인증기준", f"{len(df_criteria)}개")
k2.metric("세부 점검항목", f"{int(df_criteria['checklist_count'].sum())}개")
k3.metric("대분류", f"{df_criteria['major_category'].nunique()}개")
k4.metric(
    "미평가 항목",
    (
        f"{int(df_verdict.loc[df_verdict['verdict'] == '미평가', 'count'].sum())}"
        if not df_verdict.empty
        else "-"
    ),
)

st.divider()

# ---------------------------------------------------------------------------
# 판정 현황 + 대분류 현황
# ---------------------------------------------------------------------------
col1, col2 = st.columns(2)
with col1:
    st.subheader("🎯 판정 현황")
    if not df_verdict.empty:
        color_map = {
            "적합": "#22c55e",
            "부분적합": "#eab308",
            "부적합": "#ef4444",
            "미평가": "#9ca3af",
            "증적부족": "#f97316",
            "적용제외": "#3b82f6",
        }
        fig = px.pie(
            df_verdict,
            names="verdict",
            values="count",
            color="verdict",
            color_discrete_map=color_map,
            hole=0.4,
        )
        st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("🗂️ 대분류별 구성")
    if not df_category.empty:
        fig = px.bar(
            df_category,
            x="checklist_count",
            y="major_category",
            orientation="h",
            text="criterion_count",
            color="major_category",
            labels={
                "checklist_count": "세부 점검항목 수",
                "major_category": "대분류",
                "criterion_count": "인증기준 수",
            },
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(showlegend=False, height=380)
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# 인증기준 브라우저
# ---------------------------------------------------------------------------
st.subheader("📚 48 인증기준 선정 요약")

major_options = ["전체"] + sorted(df_criteria["major_category"].unique().tolist())
selected_major = st.selectbox("대분류", major_options, index=0, key="isms_major")

filtered = (
    df_criteria
    if selected_major == "전체"
    else df_criteria[df_criteria["major_category"] == selected_major]
)

st.dataframe(
    filtered[
        [
            "major_category",
            "section_id",
            "section_name",
            "criterion_id",
            "criterion_name",
            "checklist_count",
        ]
    ].rename(
        columns={
            "major_category": "대분류",
            "section_id": "분야 ID",
            "section_name": "분야명",
            "criterion_id": "인증기준 ID",
            "criterion_name": "인증기준명",
            "checklist_count": "점검항목 수",
        }
    ),
    use_container_width=True,
    hide_index=True,
    height=360,
)

st.divider()

# ---------------------------------------------------------------------------
# 세부 점검항목 상세
# ---------------------------------------------------------------------------
st.subheader("🔍 세부 점검항목 (법령·제재 포함)")

col_a, col_b, col_c = st.columns(3)
with col_a:
    crit_options = ["전체"] + df_criteria["criterion_id"].tolist()
    picked_crit = st.selectbox("인증기준", crit_options, index=0, key="isms_crit")
with col_b:
    verdict_options = ["전체", "미평가", "적합", "부분적합", "부적합", "증적부족", "적용제외"]
    picked_verdict = st.selectbox("판정", verdict_options, index=0, key="isms_verdict")
with col_c:
    limit = st.slider("표시 수", 20, 500, 100, step=20, key="isms_limit")

items = fetch_isms_p_checklist(
    criterion_id=None if picked_crit == "전체" else picked_crit,
    verdict=None if picked_verdict == "전체" else picked_verdict,
    limit=limit,
)

if not items:
    st.info("조건에 맞는 세부 점검항목 없음.")
else:
    df_items = pd.DataFrame(items)
    st.caption(f"조회된 세부 점검항목: {len(df_items)}개")

    for _, row in df_items.iterrows():
        with st.expander(
            f"**{row['criterion_id']}#{row['check_number']}** — "
            f"{row['check_item'][:80]}{'…' if len(row['check_item']) > 80 else ''}  "
            f"`[{row['verdict']}]`",
            expanded=False,
        ):
            st.markdown(f"**주요 점검항목**\n\n{row['check_item']}")
            if row.get("related_laws"):
                st.markdown(f"**관련 법령**\n```\n{row['related_laws']}\n```")
            if row.get("law_content"):
                with st.container():
                    st.markdown("**법령 내용**")
                    st.text(row["law_content"])
            if row.get("sanction_content"):
                st.markdown(f"**제재 내용**\n```\n{row['sanction_content']}\n```")
            if row.get("dev_summary"):
                st.markdown(f"**개발자 확인 요약**\n\n{row['dev_summary']}")
            if row.get("recommended_evidence"):
                st.markdown(f"**권장 증적**\n\n{row['recommended_evidence']}")
            if row.get("aux_standards"):
                st.caption(f"보조 기준: {row['aux_standards']}")
