"""챗봇 로그 뷰어 — 실 데이터 (`GET /logs`)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from pages._api import fetch_logs, sidebar_status

st.set_page_config(page_title="챗봇 로그", page_icon="💬", layout="wide")
st.title("💬 챗봇 로그 뷰어")
sidebar_status()

# === 필터 ===
fc1, fc2, fc3 = st.columns([1, 1, 1])
mode = fc1.selectbox("mode", options=["(all)", "internal", "external"], index=0)
since = fc2.number_input("since (id 커서)", min_value=0, value=0, step=1)
limit = fc3.slider("limit", min_value=10, max_value=1000, value=200, step=10)

mode_param = None if mode == "(all)" else mode
logs = fetch_logs(mode=mode_param, since=int(since), limit=int(limit))

if not logs:
    st.warning("조건에 맞는 로그가 없습니다.")
    st.stop()

df = pd.DataFrame(logs)

# === 강조 표시 컬럼 ===
def _badge_vuln(tag: str | None) -> str:
    return f"⚠️ {tag}" if tag else ""

def _badge_guard(rules: list) -> str:
    return "🛑 " + ",".join(rules) if rules else ""

df["vuln"] = df["intentional_vuln_tag"].apply(_badge_vuln)
df["guard"] = df["guardrail_triggered"].apply(_badge_guard)

display_cols = [
    "id", "created_at", "mode", "model_name",
    "user_input", "bot_response", "target_url",
    "vuln", "guard", "response_time_ms", "error_code",
]
st.dataframe(df[display_cols], use_container_width=True, hide_index=True)

# === 단일 row 상세 ===
st.divider()
st.subheader("단일 row 상세")
selected_id = st.selectbox("id 선택", options=df["id"].tolist())
row = df[df["id"] == selected_id].iloc[0].to_dict()
row.pop("vuln", None)
row.pop("guard", None)
st.json(row)

# TODO: request_id 클릭 → 전체 트레이스 (LLM 호출 / RAG 결과 / DB write 시간선)
# TODO: 가드레일 trigger 누르면 정책 매핑 페이지로 이동
