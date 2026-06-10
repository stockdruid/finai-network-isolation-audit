"""진단 결과 상세 — GET /diagnosis + GET /logs/{id} 실 데이터."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from pages._api import fetch_diagnoses, fetch_log_detail, sidebar_status

st.set_page_config(page_title="진단 상세", page_icon="🔍", layout="wide")
st.title("🔍 진단 결과 상세")
sidebar_status()

# ---------------------------------------------------------------------------
# 필터
# ---------------------------------------------------------------------------

fc1, fc2, fc3 = st.columns([1, 1, 1])
severity = fc1.selectbox(
    "심각도", options=["(all)", "critical", "high", "medium", "low", "info"], index=0,
)
limit = fc2.slider("표시 수", min_value=10, max_value=500, value=100, step=10)
source_filter = fc3.number_input("source_log_id (선택)", min_value=0, value=0, step=1)

severity_param = None if severity == "(all)" else severity
source_param = int(source_filter) if source_filter > 0 else None

diagnoses = fetch_diagnoses(severity=severity_param, source_log_id=source_param, limit=limit)

if not diagnoses:
    st.warning("조건에 맞는 진단 결과가 없습니다.")
    st.stop()

df = pd.DataFrame(diagnoses)

# ---------------------------------------------------------------------------
# 심각도 색상 배지
# ---------------------------------------------------------------------------

SEVERITY_COLORS = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
    "info": "⚪",
}
df["badge"] = df["severity"].map(lambda s: f"{SEVERITY_COLORS.get(s, '')} {s}")
df["correct_display"] = df["correct"].map({True: "✅", False: "❌", None: "—"})

# ---------------------------------------------------------------------------
# 테이블
# ---------------------------------------------------------------------------

left, right = st.columns([3, 2])

with left:
    st.subheader(f"진단 결과 ({len(df)}건)")
    display_cols = [
        "id", "badge", "violation_type", "matched_target_url",
        "correct_display", "source_log_id", "created_at",
    ]
    selected = st.dataframe(
        df[display_cols].rename(columns={"badge": "심각도", "correct_display": "정확"}),
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

with right:
    st.subheader("선택 상세")
    if selected and selected.selection.rows:
        row = df.iloc[selected.selection.rows[0]]
        row_dict = row.to_dict()
        # 불필요한 display 컬럼 제거
        row_dict.pop("badge", None)
        row_dict.pop("correct_display", None)

        st.json(row_dict)

        # 연관 로그 조회
        st.divider()
        st.caption("📋 연관 챗봇 로그")
        log_detail = fetch_log_detail(int(row["source_log_id"]))
        if log_detail:
            st.markdown(f"**모드**: `{log_detail['mode']}`")
            st.markdown(f"**입력**: {log_detail['user_input']}")
            st.markdown(f"**응답**: {log_detail['bot_response']}")
            if log_detail.get("target_url"):
                st.markdown(f"**대상 URL**: `{log_detail['target_url']}`")
            if log_detail.get("intentional_vuln_tag"):
                st.warning(f"의도적 취약점: `{log_detail['intentional_vuln_tag']}`")
        else:
            st.caption("로그 조회 실패")
    else:
        st.caption("좌측 행을 선택하세요")
