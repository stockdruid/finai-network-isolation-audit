"""챗봇 로그 뷰어 — 실 데이터 (`GET /logs`)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from pages._api import fetch_logs, sidebar_filters, sidebar_status

st.set_page_config(page_title="챗봇 로그", page_icon="💬", layout="wide")
st.title("💬 챗봇 로그 뷰어")
sidebar_status()
f = sidebar_filters(show_mode=True, show_limit=True)

# ---------------------------------------------------------------------------
# 데이터 로드
# ---------------------------------------------------------------------------

logs = fetch_logs(mode=f.get("mode"), limit=f.get("limit", 200))

if not logs:
    st.warning("조건에 맞는 로그가 없습니다.")
    st.stop()

df = pd.DataFrame(logs)

# ---------------------------------------------------------------------------
# 강조 표시 컬럼
# ---------------------------------------------------------------------------

def _badge_vuln(tag: str | None) -> str:
    return f"⚠️ {tag}" if tag else ""

def _badge_guard(rules: list) -> str:
    return "🛑 " + ",".join(rules) if rules else ""

df["vuln"] = df["intentional_vuln_tag"].apply(_badge_vuln)
df["guard"] = df["guardrail_triggered"].apply(_badge_guard)

# ---------------------------------------------------------------------------
# 테이블
# ---------------------------------------------------------------------------

st.subheader(f"로그 ({len(df)}건)")
display_cols = [
    "id", "created_at", "mode", "model_name",
    "user_input", "bot_response", "target_url",
    "vuln", "guard", "response_time_ms", "error_code",
]
st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# 단일 row 상세
# ---------------------------------------------------------------------------

st.divider()
st.subheader("단일 row 상세")
selected_id = st.selectbox("id 선택", options=df["id"].tolist())
row = df[df["id"] == selected_id].iloc[0].to_dict()
row.pop("vuln", None)
row.pop("guard", None)
st.json(row)
