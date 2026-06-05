"""정책 매핑 브라우저 — 법령/인증 트리 (와이어프레임, 정책팀 YAML 대기)."""
from __future__ import annotations

import streamlit as st

from pages._api import sidebar_status

st.set_page_config(page_title="정책 브라우저", page_icon="📜", layout="wide")
st.title("📜 정책 매핑 브라우저")
sidebar_status()

st.info(
    "정책팀 YAML 수령 후 활성화. 현재는 와이어프레임 — `GET /policies` 응답 모킹."
)

# === Mock 카테고리 트리 ===
mock_tree: dict[str, list[dict]] = {
    "법령": [
        {
            "code": "eFin-Reg-15",
            "title": "전자금융감독규정 제15조 (망분리)",
            "description": "금융회사는 내부 통신망과 외부 통신망을 분리하여 운영하여야 한다.",
            "severity_weight": 5,
            "related_rules": ["external_egress"],
        },
        {
            "code": "PIPA-23",
            "title": "개인정보보호법 제23조 (민감정보 처리 제한)",
            "description": "주민등록번호 등 민감정보는 별도 동의 없이 처리할 수 없다.",
            "severity_weight": 4,
            "related_rules": ["pii_ssn", "pii_card"],
        },
    ],
    "인증": [
        {
            "code": "PCI-DSS-3.4",
            "title": "PCI DSS v4 — Requirement 3.4 (PAN 보호)",
            "description": "1차 계좌번호(PAN)는 저장 시 강력한 암호화 적용.",
            "severity_weight": 4,
            "related_rules": ["pii_card"],
        },
        {
            "code": "ISMS-P-A.10.1",
            "title": "ISMS-P A.10.1 (네트워크 보안)",
            "description": "내부망과 외부망 간 트래픽 통제 및 로깅.",
            "severity_weight": 5,
            "related_rules": ["external_egress"],
        },
    ],
}

category = st.radio("카테고리", options=list(mock_tree.keys()), horizontal=True)
items = mock_tree[category]

for item in items:
    with st.expander(f"**{item['code']}** — {item['title']}"):
        st.write(item["description"])
        st.caption(f"심각도 가중치: {item['severity_weight']}")
        st.write("연계 룰:")
        st.code(", ".join(item["related_rules"]))

# TODO: 정책팀 YAML → DB 적재 후 GET /policies 연동
# TODO: 진단 결과의 regulation_reference 클릭 시 이 페이지로 라우팅
