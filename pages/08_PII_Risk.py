"""개인정보 위험도 산정체계 페이지.

- 유형별 위험도 점수 표
- 위험 등급 기준 (Critical/High/Medium/Low)
- PII 필드 스코어링 계산기 (실시간 등급 판정)
- 챗봇 로그 pii_fields 기반 위험도 KPI

원천: 정책팀 자료 `개인정보_위험도_산정체계.xlsx` (2026-07-07).
"""
from __future__ import annotations

from collections import Counter

import pandas as pd
import plotly.express as px
import streamlit as st

from pages._api import (
    fetch_logs,
    fetch_pii_risk_levels,
    fetch_pii_types,
    score_pii_fields,
    sidebar_status,
)

st.set_page_config(page_title="개인정보 위험도", page_icon="🛡️", layout="wide")
st.title("🛡️ 개인정보 위험도 산정")
st.caption("정책팀 산정체계 — 유형별 점수 + 등급 판정 + 챗봇 로그 위험도 실시간 계산")

sidebar_status()

pii_types = fetch_pii_types()
levels = fetch_pii_risk_levels()

if not pii_types or not levels:
    st.warning("데이터가 없다. `scripts/import_pii_risk.py` 실행 필요.")
    st.stop()

df_types = pd.DataFrame(pii_types)
df_levels = pd.DataFrame(levels)

# ---------------------------------------------------------------------------
# KPI — 챗봇 로그 위험도
# ---------------------------------------------------------------------------
st.subheader("📊 챗봇 로그 기반 PII 위험도 (실시간)")

logs = fetch_logs(limit=500)
pii_logs = [lg for lg in logs if lg.get("pii_detected") and lg.get("pii_fields")]
detected_fields: list[str] = []
for lg in pii_logs:
    fields = lg.get("pii_fields") or []
    if isinstance(fields, list):
        detected_fields.extend([str(f) for f in fields])

field_counts = Counter(detected_fields)
type_score_map = {r["name"]: float(r["risk_score"]) for r in pii_types}
total_score = sum(
    type_score_map.get(f, 0.0) * cnt for f, cnt in field_counts.items()
)

# 등급 판정
picked = None
for lv in sorted(levels, key=lambda x: -float(x["min_score"])):
    if total_score >= float(lv["min_score"]):
        picked = lv
        break

k1, k2, k3, k4 = st.columns(4)
k1.metric("PII 탐지 로그", f"{len(pii_logs)}건")
k2.metric("유출 유형 수", f"{len(field_counts)}종")
k3.metric("합산 위험 점수", f"{total_score:.1f}점")
k4.metric(
    "현재 등급",
    f"{picked['level_en']} ({picked['level_ko']})" if picked else "-",
)

if picked:
    color_map = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}
    st.info(
        f"{color_map.get(picked['level_en'], '⚪')} **{picked['level_en']} — "
        f"{picked['action_level']}** · {picked['description']}"
    )

st.divider()

# ---------------------------------------------------------------------------
# 등급 기준 표
# ---------------------------------------------------------------------------
st.subheader("📏 위험 등급 기준")
st.dataframe(
    df_levels[["level_en", "level_ko", "score_range", "action_level", "description"]]
    .rename(
        columns={
            "level_en": "등급 (EN)",
            "level_ko": "등급 (KO)",
            "score_range": "점수 범위",
            "action_level": "조치 수준",
            "description": "설명",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

st.divider()

# ---------------------------------------------------------------------------
# 유형별 위험도
# ---------------------------------------------------------------------------
st.subheader("🧾 개인정보 유형별 위험도")

col1, col2 = st.columns([2, 1])
with col1:
    fig = px.bar(
        df_types.sort_values("risk_score", ascending=True),
        x="risk_score",
        y="name",
        orientation="h",
        color="risk_score",
        color_continuous_scale=["#22c55e", "#eab308", "#ef4444"],
        title="유형별 최종 위험도 점수",
        labels={"risk_score": "위험도", "name": "PII 유형"},
    )
    fig.update_layout(height=520, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    df_top = df_types.sort_values("risk_score", ascending=False)[
        ["name", "risk_score"]
    ].head(10)
    st.markdown("**Top 10 고위험**")
    for _, row in df_top.iterrows():
        st.markdown(f"- **{row['name']}** — `{row['risk_score']}점`")

with st.expander("📖 전체 유형 상세 (법령 근거 포함)", expanded=False):
    st.dataframe(
        df_types[["name", "risk_score", "weight_label", "legal_basis"]].rename(
            columns={
                "name": "PII 유형",
                "risk_score": "위험도",
                "weight_label": "가중치",
                "legal_basis": "법령 근거",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

st.divider()

# ---------------------------------------------------------------------------
# 스코어링 계산기
# ---------------------------------------------------------------------------
st.subheader("🧮 PII 스코어링 계산기")
st.caption("복합 유출 시나리오의 등급을 계산해 본다.")

selected = st.multiselect(
    "탐지된 PII 유형 선택",
    options=[r["name"] for r in pii_types],
    default=[],
)
if selected:
    result = score_pii_fields(selected)
    if result:
        col_a, col_b = st.columns(2)
        col_a.metric("합산 위험 점수", f"{result['total_score']}점")
        lvl = result.get("level")
        if lvl:
            col_b.metric(
                "판정 등급",
                f"{lvl['level_en']} ({lvl['level_ko']})",
                delta=lvl["action_level"],
            )
        matched = result.get("matched") or []
        if matched:
            st.dataframe(
                pd.DataFrame(matched)[["name", "risk_score", "legal_basis"]].rename(
                    columns={
                        "name": "PII 유형",
                        "risk_score": "위험도",
                        "legal_basis": "법령 근거",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )
