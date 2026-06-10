"""정책 매핑 브라우저 — GET /policies 실 데이터."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from pages._api import fetch_policies, sidebar_status

st.set_page_config(page_title="정책 브라우저", page_icon="📜", layout="wide")
st.title("📜 정책 매핑 브라우저")
sidebar_status()

# ---------------------------------------------------------------------------
# 데이터 로드
# ---------------------------------------------------------------------------

policies = fetch_policies()
if not policies:
    st.warning("정책 데이터가 없습니다. `scripts/load_policies.py` 실행 후 새로고침하세요.")
    st.stop()

df = pd.DataFrame(policies)
categories = sorted(df["category"].unique().tolist())

# ---------------------------------------------------------------------------
# 카테고리 필터
# ---------------------------------------------------------------------------

selected_cat = st.radio("카테고리", options=["전체"] + categories, horizontal=True)

if selected_cat != "전체":
    filtered = df[df["category"] == selected_cat]
else:
    filtered = df

# ---------------------------------------------------------------------------
# 통계 카드
# ---------------------------------------------------------------------------

c1, c2, c3 = st.columns(3)
c1.metric("정책 수", len(filtered))
c2.metric("카테고리", filtered["category"].nunique())
c3.metric("평균 심각도 가중치", f"{filtered['severity_weight'].mean():.1f}")

st.divider()

# ---------------------------------------------------------------------------
# 정책 목록
# ---------------------------------------------------------------------------

for _, row in filtered.iterrows():
    severity_bar = "🔴" if row["severity_weight"] >= 8.0 else "🟠" if row["severity_weight"] >= 6.0 else "🟢"
    with st.expander(f"{severity_bar} **{row['code']}** — {row['title']}  `{row['category']}`"):
        if row.get("description"):
            st.write(row["description"])

        col1, col2 = st.columns(2)
        with col1:
            st.caption(f"심각도 가중치: **{row['severity_weight']}**")
        with col2:
            st.caption(f"카테고리: **{row['category']}**")

        rules = row.get("related_rules", [])
        if rules:
            st.markdown("**관련 법령/규정:**")
            for rule in rules:
                if isinstance(rule, dict):
                    st.markdown(f"- {rule.get('law', '')} {rule.get('section', '')}")
                else:
                    st.markdown(f"- {rule}")
