"""메인 대시보드 — 컴플라이언스 점수, 정확도, 위반 분포."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from pages._api import fetch_logs, sidebar_status

st.set_page_config(page_title="진단 대시보드", page_icon="📊", layout="wide")
st.title("📊 진단 대시보드")
sidebar_status()

logs = fetch_logs(limit=1000)
if not logs:
    st.warning("아직 로그가 없습니다. `POST /chat` 호출 후 새로고침하세요.")
    st.stop()

df = pd.DataFrame(logs)
external_df = df[df["mode"] == "external"]

# === KPI 카드 ===
c1, c2, c3, c4 = st.columns(4)
c1.metric("총 호출", len(df))
c2.metric("외부 호출 (위반 후보)", len(external_df))
c3.metric(
    "가드레일 트리거",
    int(df["guardrail_triggered"].apply(lambda x: len(x) > 0).sum()),
)
intentional = external_df["intentional_vuln_tag"].notna().sum()
c4.metric(
    "intentional_vuln_tag 적중률",
    f"{intentional}/{len(external_df)}" if len(external_df) else "0/0",
    help="진단 엔진이 매칭한 의도적 취약점 수 (개발자 B insert 후 정확도 컬럼 활용)",
)

st.divider()

# === 모드별 분포 ===
left, right = st.columns(2)
with left:
    st.subheader("호출 모드 분포")
    mode_counts = df["mode"].value_counts().reset_index()
    mode_counts.columns = ["mode", "count"]
    fig = px.pie(mode_counts, names="mode", values="count", hole=0.4)
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("시간대별 호출 추이")
    df["created_at"] = pd.to_datetime(df["created_at"])
    timeline = (
        df.set_index("created_at")
        .resample("1min")
        .size()
        .reset_index(name="count")
    )
    fig = px.line(timeline, x="created_at", y="count", markers=True)
    st.plotly_chart(fig, use_container_width=True)

# === 외부 호출 대상 도메인 ===
st.subheader("외부 호출 대상 도메인 (망분리 위반 후보)")
if external_df.empty:
    st.info("외부 호출 기록 없음.")
else:
    domain_counts = external_df["target_url"].value_counts().reset_index()
    domain_counts.columns = ["target_url", "count"]
    fig = px.bar(domain_counts, x="target_url", y="count")
    st.plotly_chart(fig, use_container_width=True)

# TODO: GET /diagnosis 연동 → 심각도 분포, 진단 엔진 정확도 카드, 규제 매핑 차트
