"""진단 결과 상세 — `/diagnosis` 엔드포인트 대기 중 (와이어프레임)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from pages._api import sidebar_status

st.set_page_config(page_title="진단 상세", page_icon="🔍", layout="wide")
st.title("🔍 진단 결과 상세")
sidebar_status()

st.info(
    "이 페이지는 진단 엔진(개발자 B) 결과 적재 후 활성화됩니다. "
    "현재는 와이어프레임 — `GET /diagnosis` 응답 모킹."
)

# === Mock 데이터 ===
mock = pd.DataFrame(
    [
        {
            "id": 1,
            "source_log_id": 2,
            "created_at": "2026-06-05T14:10:11+09:00",
            "violation_type": "external_egress",
            "severity": "critical",
            "matched_target_url": "api.openai-mock.example.com",
            "regulation_reference": ["eFin-Reg-15"],
            "correct": True,
        },
        {
            "id": 2,
            "source_log_id": 3,
            "created_at": "2026-06-05T14:12:34+09:00",
            "violation_type": "pii_leak",
            "severity": "high",
            "matched_target_url": None,
            "regulation_reference": ["PCI-DSS-3.4", "PIPA-23"],
            "correct": False,
        },
    ]
)

left, right = st.columns([2, 1])
with left:
    st.subheader("진단 결과 목록")
    selected = st.dataframe(
        mock,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

with right:
    st.subheader("선택 상세")
    if selected and selected.selection.rows:
        row = mock.iloc[selected.selection.rows[0]]
        st.json(row.to_dict())
    else:
        st.caption("좌측 행 선택")

# TODO: GET /diagnosis 연동 시 mock 제거
# TODO: source_log_id → chatbot_logs row 조인 (`GET /logs/{id}` 신설 후)
# TODO: 규제 매핑 클릭 시 정책 브라우저 페이지로 이동
