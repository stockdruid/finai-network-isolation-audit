"""망분리 시각화 페이지 — Phase 3 발표 임팩트 구간.

4개 탭:
    1. 타임라인 — 챗봇 이벤트의 시간 흐름 + 외부 호출 하이라이트
    2. 위반 플로우 — 정상 경로 vs 위반 경로 비교
    3. AWS 아키텍처 — VPC A/B 구조·EC2 배치·트래픽 흐름
    4. 토스 비교 — 토스 실제 사례 vs 우리 시뮬레이션 병렬

원천 데이터: chatbot_logs (실 로그 16건).
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from pages._api import fetch_logs, sidebar_status


def render_mermaid(code: str, height: int = 400) -> None:
    """Streamlit에서 Mermaid 다이어그램 렌더링 — mermaid.js CDN 사용."""
    html = f"""
    <div class="mermaid" style="text-align:center;">{code}</div>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <script>
        mermaid.initialize({{startOnLoad: true, theme: 'default', securityLevel: 'loose'}});
    </script>
    """
    components.html(html, height=height, scrolling=False)

st.set_page_config(page_title="망분리 시각화", page_icon="🛰️", layout="wide")
st.title("🛰️ 망분리 시각화")
st.caption("VPC 경계 · 외부 호출 · 위반 시나리오 — 발표 임팩트 구간")

sidebar_status()

# ---------------------------------------------------------------------------
# 데이터 로드
# ---------------------------------------------------------------------------
logs = fetch_logs(limit=1000)
if not logs:
    st.warning("chatbot_logs가 비었다. `scripts/import_chatbot_logs.py --reset` 실행 필요.")
    st.stop()

df = pd.DataFrame(logs)
df["created_at"] = pd.to_datetime(df["created_at"])

# 이벤트 분류
def _classify(row) -> str:
    if row.get("status") == "blocked":
        return "🛡️ 가드레일 차단"
    if row.get("mode") == "external":
        return "🚨 망분리 위반 (외부 LLM)"
    if row.get("intentional_vuln_tag"):
        return "⚠️ PII 유출 의심"
    if row.get("event_type") in ("signup", "login"):
        return "🔐 인증 이벤트"
    return "✅ 내부 정상"

df["classification"] = df.apply(_classify, axis=1)

CLASS_COLORS = {
    "✅ 내부 정상": "#2ecc71",
    "⚠️ PII 유출 의심": "#f39c12",
    "🛡️ 가드레일 차단": "#3498db",
    "🚨 망분리 위반 (외부 LLM)": "#e74c3c",
    "🔐 인증 이벤트": "#9b59b6",
}

# ---------------------------------------------------------------------------
# 최상단 KPI
# ---------------------------------------------------------------------------
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("총 이벤트", len(df))
c2.metric("외부 호출", int((df["mode"] == "external").sum()))
c3.metric("PII 탐지", int(df["pii_detected"].sum()))
c4.metric("가드레일 차단", int((df["status"] == "blocked").sum()))
c5.metric("위반 태그", int(df["intentional_vuln_tag"].notna().sum()))

st.divider()

# ---------------------------------------------------------------------------
# 탭 4종
# ---------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs(
    ["⏱️ 타임라인", "🔀 위반 플로우", "🌐 AWS 아키텍처", "⚖️ 토스 비교"]
)

# ==========================================================================
# 탭 1: 타임라인
# ==========================================================================
with tab1:
    st.subheader("⏱️ 챗봇 이벤트 타임라인")
    st.caption("외부 LLM 호출·PII 탐지·가드레일 차단이 언제 발생했는지 시간 축으로 표시")

    # 스캐터 타임라인
    fig_t = px.scatter(
        df,
        x="created_at",
        y="classification",
        color="classification",
        color_discrete_map=CLASS_COLORS,
        hover_data={
            "created_at": True,
            "event_type": True,
            "target_provider": True,
            "target_url": True,
            "intentional_vuln_tag": True,
            "user_input": True,
            "classification": False,
        },
        size_max=15,
        title="시간 흐름 · 이벤트 유형별 발생",
    )
    fig_t.update_traces(marker=dict(size=14, line=dict(width=1, color="white")))
    fig_t.update_layout(height=450, showlegend=True)
    st.plotly_chart(fig_t, use_container_width=True)

    # 이벤트 분류 카운트
    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.markdown("**이벤트 분류 카운트**")
        class_counts = df["classification"].value_counts().reset_index()
        class_counts.columns = ["classification", "count"]
        fig_cnt = px.bar(
            class_counts,
            x="count",
            y="classification",
            orientation="h",
            color="classification",
            color_discrete_map=CLASS_COLORS,
        )
        fig_cnt.update_layout(showlegend=False, height=300)
        st.plotly_chart(fig_cnt, use_container_width=True)

    with col_b:
        st.markdown("**위반·차단 이벤트 상세**")
        violations = df[
            (df["mode"] == "external")
            | (df["status"] == "blocked")
            | df["intentional_vuln_tag"].notna()
        ][
            ["created_at", "classification", "event_type", "target_provider",
             "intentional_vuln_tag", "pii_detected", "user_input"]
        ]
        st.dataframe(violations, use_container_width=True, height=300)

# ==========================================================================
# 탭 2: 위반 플로우
# ==========================================================================
with tab2:
    st.subheader("🔀 정상 경로 vs 망분리 위반 경로")
    st.caption("같은 챗봇 요청이 어디로 흘러가느냐에 따라 컴플라이언스 판정이 갈린다")

    col_ok, col_bad = st.columns(2)

    with col_ok:
        st.markdown("### ✅ 정상 (mode=internal)")
        render_mermaid(
            """
flowchart LR
    U([사용자]) --> UI[Streamlit 챗봇]
    UI -->|POST /chat| API[FastAPI]
    API --> R{LLM Router}
    R -->|internal| OL[🦙 Ollama<br/>VPC A 내부]
    OL --> LOG[(chatbot_logs<br/>target_provider=ollama)]
    LOG --> D[진단: 위반 없음]
    style OL fill:#d5f5e3,stroke:#27ae60
    style D fill:#d5f5e3,stroke:#27ae60
""",
            height=380,
        )
        clean_sample = df[
            (df["mode"] == "internal")
            & (df["target_provider"] == "ollama")
            & df["intentional_vuln_tag"].isna()
        ].head(1)
        if not clean_sample.empty:
            row = clean_sample.iloc[0]
            st.success(
                f"**실 로그 예시**\n\n"
                f"- 입력: {row['user_input'][:80]}\n"
                f"- target: `{row['target_url']}`\n"
                f"- 판정: **위반 없음**"
            )

    with col_bad:
        st.markdown("### 🚨 위반 (mode=external)")
        render_mermaid(
            """
flowchart LR
    U([사용자]) --> UI[Streamlit 챗봇]
    UI -->|POST /chat| API[FastAPI]
    API --> R{LLM Router}
    R -.->|external<br/>⚠️ VPC 경계 넘음| EX[🎭 Mock External LLM<br/>VPC B]
    EX --> LOG[(chatbot_logs<br/>target_url != null<br/>vuln_tag=EV-001)]
    LOG --> D[진단: 전자금융감독규정<br/>제15조 위반]
    style EX fill:#fadbd8,stroke:#e74c3c,stroke-dasharray: 5 5
    style D fill:#fadbd8,stroke:#e74c3c
""",
            height=380,
        )
        violation_sample = df[df["mode"] == "external"].head(1)
        if not violation_sample.empty:
            row = violation_sample.iloc[0]
            st.error(
                f"**실 로그 예시 (EV-001)**\n\n"
                f"- 입력: {row['user_input'][:80]}\n"
                f"- target: `{row['target_url']}`\n"
                f"- 태그: `{row['intentional_vuln_tag']}`\n"
                f"- PII: {row['pii_detected']}"
            )

    st.divider()
    st.markdown("### 📋 탐지 규칙")
    st.markdown(
        """
1. **`chatbot_logs.target_url`이 NULL이 아닌 모든 row** → 외부 호출 후보
2. **도메인 화이트리스트** 대조 (`localhost:11434` = 내부 Ollama, 그 외 = 위반 후보)
3. **`policy_mappings`의 전자금융감독규정 제15조**에 자동 매핑
4. **`requirements`의 GAI-1.x / CLD-01~ / SAA-01~** 항목과 크로스 참조
"""
    )

# ==========================================================================
# 탭 3: AWS 아키텍처
# ==========================================================================
with tab3:
    st.subheader("🌐 AWS 인프라 (5인 팀 축소 시뮬레이션)")
    st.caption("금융권 실 인프라를 VPC 2개 · EC2 2~3대 · S3 · CloudWatch로 축소")

    render_mermaid(
        """
flowchart TB
    Internet([🌐 Internet])

    subgraph AWS["AWS 계정 (finai-compliance)"]
        direction TB

        subgraph VPCA["VPC A · 10.0.0.0/16 · 내부망 (금융 프로덕션)"]
            direction TB
            IGW1[Internet Gateway<br/>= 외부 접근점 = 위반 후보]

            subgraph SubA1["Public Subnet 10.0.1.0/24"]
                ALB[ALB<br/>Streamlit :443]
            end

            subgraph SubA2["Private Subnet 10.0.2.0/24"]
                EC2_APP[EC2 · Streamlit+FastAPI<br/>t3.medium]
                EC2_LLM[EC2 · Ollama qwen2.5:7b<br/>g4dn.xlarge]
            end

            subgraph SubA3["Private Subnet 10.0.3.0/24"]
                RDS[(RDS PostgreSQL 15<br/>chatbot_logs·매핑 8종)]
                CHR[(EFS · ChromaDB)]
            end
        end

        subgraph VPCB["VPC B · 10.1.0.0/16 · 외부 LLM 시뮬"]
            EC2_MOCK[EC2 · Mock LLM<br/>api.openai-mock.example.com<br/>t3.small]
        end

        S3[(S3 · finai-reports<br/>리포트·정책 YAML)]
        CW[CloudWatch Logs<br/>+ 알람]
    end

    Internet --> IGW1
    IGW1 --> ALB
    ALB --> EC2_APP
    EC2_APP --> EC2_LLM
    EC2_APP --> RDS
    EC2_APP --> CHR
    EC2_APP -.->|⚠️ EV-001<br/>VPC 경계 위반| EC2_MOCK
    EC2_APP --> S3
    EC2_APP --> CW
    EC2_LLM --> CW
    RDS --> CW

    classDef violation stroke:#e74c3c,stroke-width:3px,stroke-dasharray:5 5
    classDef safe stroke:#27ae60,stroke-width:2px
    class EC2_MOCK violation
    class EC2_LLM,RDS,CHR safe
""",
        height=800,
    )

    with st.expander("💰 인스턴스 사이징 · 비용 근거"):
        st.markdown(
            """
| 컴포넌트 | 인스턴스 | 이유 |
|---------|---------|------|
| App EC2 | t3.medium | Streamlit+FastAPI 동시 5인 팀 데모 |
| Ollama EC2 | g4dn.xlarge | qwen2.5:7b GPU 추론, VRAM 16GB |
| Mock LLM EC2 | t3.small | 응답 1회 / 요청, 부하 낮음 |
| RDS PostgreSQL 15 | db.t3.micro | 로그·매핑 총 1GB 미만 |
| ChromaDB | EFS | 임베딩 파일 공유, 벡터 검색 |
"""
        )

# ==========================================================================
# 탭 4: 토스 비교
# ==========================================================================
with tab4:
    st.subheader("⚖️ 토스 실제 사례 vs 우리 시뮬레이션")
    st.caption("금융권 최초 생성형 AI 챗봇 승인 사례를 기준으로 시뮬레이션 구성")

    col_toss, col_ours = st.columns(2)

    with col_toss:
        st.markdown("### 🏦 토스 (실 사례, 2024 승인)")
        st.markdown(
            """
- **샌드박스 승인**: 금융위원회, 2024
- **아키텍처**: VPC 내부 + 별도 AI VPC (VPC Peering)
- **외부 LLM**: OpenAI · Anthropic (VPC 경계 통과, Private Link)
- **가드레일**: PII 마스킹 → 프롬프트 검증 → 응답 검증
- **로그**: CloudWatch + S3 감사 로그 (30일 보관)
- **규제**: 전자금융감독규정 제15조 특례 승인
"""
        )

    with col_ours:
        st.markdown("### 🎓 우리 (5인 팀 시뮬레이션)")
        st.markdown(
            """
- **범위**: 승인 없이 위반 시나리오 자동 탐지
- **아키텍처**: VPC A(내부) + VPC B(외부 시뮬), 실제 승인 없음
- **외부 LLM**: Mock 서버 (openai-mock.example.com)
- **가드레일**: `guardrail_triggered` 필드 · `ssn_pattern` 등 4종
- **로그**: `chatbot_logs` 24컬럼 (`raw_request`/`raw_response` 포함)
- **규제 매핑**: `requirements` 268건 → `common_controls` 25건
"""
        )

    st.divider()
    st.markdown("### 📊 대응 표")
    comparison = pd.DataFrame(
        {
            "항목": ["외부 LLM 호출", "PII 처리", "로그 보관", "규제 준수 근거", "가드레일"],
            "토스 (실 승인)": [
                "OpenAI/Anthropic Private Link",
                "마스킹 후 전송",
                "CloudWatch + S3 30일",
                "샌드박스 특례",
                "3단계 검증",
            ],
            "우리 (시뮬)": [
                "Mock LLM (VPC B)",
                "감지만, 마스킹 미구현",
                "PostgreSQL chatbot_logs 무제한",
                "268건 매핑 traceability",
                "guardrail_triggered 4종",
            ],
        }
    )
    st.dataframe(comparison, use_container_width=True, hide_index=True)
