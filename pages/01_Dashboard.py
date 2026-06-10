"""메인 대시보드 — 컴플라이언스 점수, 진단 정확도, 위반 분포, 타임라인."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from pages._api import (
    fetch_logs,
    fetch_stats_overview,
    fetch_stats_severity,
    fetch_stats_timeline,
    fetch_stats_violations,
    generate_report,
    sidebar_filters,
    sidebar_status,
)

st.set_page_config(page_title="진단 대시보드", page_icon="📊", layout="wide")
st.title("📊 진단 대시보드")
sidebar_status()
f = sidebar_filters(show_period=True, show_mode=True)

# ---------------------------------------------------------------------------
# KPI 카드
# ---------------------------------------------------------------------------

overview = fetch_stats_overview()
if not overview:
    st.warning("API 연결을 확인하세요.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("총 로그", overview.get("total_logs", 0))
c2.metric("총 진단", overview.get("total_diagnoses", 0))
c3.metric(
    "진단 정확도",
    f"{overview.get('accuracy', 0)}%",
    help="intentional_vuln_tag 대비 진단 엔진 correct 비율",
)
c4.metric(
    "위반 탐지",
    overview.get("violations_detected", 0),
    delta=f"정확 {overview.get('correct_detections', 0)}건",
    delta_color="normal",
)

st.divider()

# ---------------------------------------------------------------------------
# 차트 — 심각도 분포 + 위반 유형
# ---------------------------------------------------------------------------

left, right = st.columns(2)

with left:
    st.subheader("심각도별 분포")
    severity_data = fetch_stats_severity()
    if severity_data:
        df_sev = pd.DataFrame(severity_data)
        color_map = {
            "critical": "#dc3545",
            "high": "#fd7e14",
            "medium": "#ffc107",
            "low": "#20c997",
            "info": "#6c757d",
        }
        fig = px.pie(
            df_sev, names="severity", values="count", hole=0.45,
            color="severity", color_discrete_map=color_map,
        )
        fig.update_traces(textinfo="label+value")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("진단 데이터 없음")

with right:
    st.subheader("위반 유형별 통계")
    violation_data = fetch_stats_violations()
    if violation_data:
        df_viol = pd.DataFrame(violation_data)
        fig = px.bar(
            df_viol, x="count", y="violation_type", orientation="h",
            color="count", color_continuous_scale="Reds",
        )
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("진단 데이터 없음")

# ---------------------------------------------------------------------------
# 차트 — 시간대별 추이
# ---------------------------------------------------------------------------

st.subheader("시간대별 진단 추이")
timeline_data = fetch_stats_timeline(days=f.get("period", 30))
if timeline_data:
    df_tl = pd.DataFrame(timeline_data)
    df_tl["date"] = pd.to_datetime(df_tl["date"])
    fig = px.area(df_tl, x="date", y="count", markers=True)
    fig.update_layout(xaxis_title="날짜", yaxis_title="진단 수")
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("해당 기간 진단 데이터 없음")

# ---------------------------------------------------------------------------
# 호출 모드 분포 (로그 기반)
# ---------------------------------------------------------------------------

st.divider()

left2, right2 = st.columns(2)

logs = fetch_logs(mode=f.get("mode"), limit=1000)

with left2:
    st.subheader("호출 모드 분포")
    if logs:
        df_logs = pd.DataFrame(logs)
        mode_counts = df_logs["mode"].value_counts().reset_index()
        mode_counts.columns = ["mode", "count"]
        fig = px.pie(mode_counts, names="mode", values="count", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("로그 없음")

with right2:
    st.subheader("외부 호출 대상 도메인")
    if logs:
        ext_df = df_logs[df_logs["mode"] == "external"]
        if not ext_df.empty:
            domain_counts = ext_df["target_url"].value_counts().reset_index()
            domain_counts.columns = ["target_url", "count"]
            fig = px.bar(domain_counts, x="target_url", y="count")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("외부 호출 없음")

# ---------------------------------------------------------------------------
# 리포트 생성
# ---------------------------------------------------------------------------

st.divider()
st.subheader("📄 컴플라이언스 리포트 생성")
if st.button("현재 데이터 기준 리포트 생성"):
    with st.spinner("리포트 생성 중..."):
        report = generate_report()
    if report:
        st.success(f"리포트 생성 완료 (ID: {report['id']}, Score: {report['total_score']})")
        st.json(report)
