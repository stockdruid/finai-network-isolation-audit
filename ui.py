"""금융 챗봇 임시 UI (Streamlit).

실행: PYTHONPATH=. uv run streamlit run ui/streamlit_app.py
필요: 챗봇 API(8000), mock LLM(9999), Postgres가 모두 떠있어야 함.

흐름: 로그인/회원가입 → 챗봇 대화(internal/external) → 사이드바에서 로그 확인
"""

import os
import uuid

import httpx
import streamlit as st

API_BASE = os.getenv("CHATBOT_API_URL", "http://localhost:8000")


# --- API 호출 ---
def call_signup(payload: dict) -> dict:
    r = httpx.post(f"{API_BASE}/auth/signup", json=payload, timeout=10.0)
    if r.status_code >= 400:
        return {"error": r.json().get("detail", "signup failed")}
    return r.json()


def call_login(username: str, password: str) -> dict:
    r = httpx.post(
        f"{API_BASE}/auth/login",
        json={"username": username, "password": password},
        timeout=10.0,
    )
    if r.status_code >= 400:
        return {"error": r.json().get("detail", "login failed")}
    return r.json()


def call_chat(prompt: str, mode: str, conversation_id: str, token: str | None = None) -> dict:
    # 세션 토큰을 보내면 서버가 user_id를 로그에 남긴다 (진단 엔진 행위 추적용)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = httpx.post(
        f"{API_BASE}/chat",
        json={"prompt": prompt, "mode": mode, "conversation_id": conversation_id},
        headers=headers,
        timeout=120.0,
    )
    if r.status_code == 403:
        return {"error": "guardrail_blocked", "detail": r.json()}
    r.raise_for_status()
    return r.json()


def fetch_recent_logs(limit: int = 5) -> list[dict]:
    try:
        r = httpx.get(f"{API_BASE}/logs", params={"limit": limit}, timeout=5.0)
        r.raise_for_status()
        _d = r.json(); return _d if isinstance(_d, list) else _d.get("items", [])
    except Exception:
        return []


# --- 페이지 설정 ---
st.set_page_config(page_title="금융 챗봇", page_icon="💰", layout="wide")

# --- 로그인 게이트 ---
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.title("💰 금융 챗봇 로그인")
    st.caption("데모용 로그인 — 비밀번호/개인정보는 평문 저장됩니다(의도적 취약점).")

    tab_login, tab_signup = st.tabs(["로그인", "회원가입"])

    with tab_login:
        with st.form("login_form"):
            lu = st.text_input("아이디")
            lp = st.text_input("비밀번호", type="password")
            if st.form_submit_button("로그인"):
                res = call_login(lu, lp)
                if res.get("error"):
                    st.error(f"로그인 실패: {res['error']}")
                else:
                    st.session_state.user = res
                    st.rerun()

    with tab_signup:
        with st.form("signup_form"):
            su = st.text_input("아이디 (3자 이상)")
            sp = st.text_input("비밀번호", type="password")
            st.caption("아래 개인정보는 선택 입력 — 넣으면 평문 저장됩니다.")
            ssn = st.text_input("주민등록번호 (선택)")
            phone = st.text_input("전화번호 (선택)")
            email = st.text_input("이메일 (선택)")
            if st.form_submit_button("회원가입"):
                payload = {"username": su, "password": sp}
                if ssn:
                    payload["ssn"] = ssn
                if phone:
                    payload["phone"] = phone
                if email:
                    payload["email"] = email
                res = call_signup(payload)
                if res.get("error"):
                    st.error(f"회원가입 실패: {res['error']}")
                else:
                    st.session_state.user = res
                    st.success("회원가입 완료! 바로 로그인되었습니다.")
                    st.rerun()

    st.stop()  # 로그인 전에는 챗봇 화면 안 보임


# --- 로그인 이후: session state 초기화 ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())

# --- 사이드바 ---
with st.sidebar:
    st.markdown(f"👤 **{st.session_state.user['username']}** 님")
    if st.button("로그아웃"):
        st.session_state.user = None
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.markdown("### ⚙️ 설정")

    mode = st.radio(
        "LLM 모드",
        ["internal", "external"],
        format_func=lambda x: "🟢 internal (안전)" if x == "internal" else "🚨 external (위반 시뮬)",
    )

    st.caption(f"대화 ID: `{st.session_state.conversation_id[:8]}...`")

    if st.button("🔄 새 대화 시작"):
        st.session_state.messages = []
        st.session_state.conversation_id = str(uuid.uuid4())
        st.rerun()

    st.divider()

    st.markdown("### 📋 최근 로그 5건")
    if st.button("새로고침", key="refresh_logs"):
        st.rerun()

    for log in fetch_recent_logs(limit=5):
        mode_icon = "🚨" if log["mode"] == "external" else "🟢"
        vuln = log.get("intentional_vuln_tag") or ""
        if log.get("status") == "blocked":
            tag = f"🛑 BLOCKED ({log.get('guardrail_triggered')})"
        elif vuln:
            tag = f"⚠️ {vuln}"
        else:
            tag = "✅ 안전"
        st.caption(f"{mode_icon} {tag} — `{log['user_prompt'][:25]}...`")

# --- 메인 ---
st.title("💰 금융 챗봇")
st.caption("예적금 · 개인신용대출 · 카드 추천")

if mode == "external":
    st.error("🚨 **external 모드** — 외부 LLM(VPC B mock)을 호출합니다. 망분리 규제 위반 시나리오(EV-001)입니다.")

# 채팅 히스토리 출력
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("meta"):
            st.caption(msg["meta"])

# 입력
if prompt := st.chat_input("질문해보세요 (예: 적금 추천해줘)"):
    # 사용자 메시지 추가
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # API 호출
    with st.chat_message("assistant"):
        with st.spinner("답변 생성 중..."):
            result = call_chat(
                prompt,
                mode,
                st.session_state.conversation_id,
                token=st.session_state.user.get("session_token"),
            )

        if result.get("error") == "guardrail_blocked":
            detail = result["detail"]["detail"]
            content = f"🛑 가드레일에 의해 차단되었습니다. (규칙: `{detail.get('rule')}`)"
            meta = None
        else:
            content = result["response"]
            meta = f"mode: {result['mode']} | latency: {result['latency_ms']}ms"

        st.markdown(content)
        if meta:
            st.caption(meta)

    st.session_state.messages.append({"role": "assistant", "content": content, "meta": meta})
    st.rerun()  # 사이드바 로그 즉시 갱신
