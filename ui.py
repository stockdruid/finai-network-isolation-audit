"""Streamlit UI 엔트리 — 챗봇 페이지 (개발자 A) + 대시보드 페이지 사이드바.

`streamlit run ui.py` 실행 시:
    - 이 파일이 홈 페이지 (챗봇)
    - pages/01_Dashboard, 02_Diagnosis_Detail, 03_Chatbot_Logs, 04_Policy_Browser
      자동으로 사이드바에 표시됨
"""
from __future__ import annotations

import streamlit as st

from pages._api import sidebar_status

st.set_page_config(page_title="finai 챗봇", page_icon="💬", layout="wide")
st.title("💬 금융 AI 챗봇")
sidebar_status()

st.info(
    "이 페이지는 개발자 A가 채팅 UI를 구현합니다. "
    "사이드바에서 진단 대시보드 / 챗봇 로그 / 정책 브라우저로 이동 가능."
)

# TODO(개발자 A):
#   - mode 토글 (internal / external)
#   - st.chat_input + st.chat_message
#   - POST {FASTAPI_BASE_URL}/chat (request body: {user_input, mode})
#   - 응답 표시
#   - 가드레일 trigger / vuln_tag 발생 시 배지 표시
