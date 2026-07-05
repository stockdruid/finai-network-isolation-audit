from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import re
import json

app = FastAPI(title="Financial-Security-Compliance-Engine", version="1.0.0")


class ComplianceRuleEngine:

    def __init__(self):
        # 1. PII 및 중요정보 패턴
        self.pii_patterns = {
            "전화번호": r"010-\d{4}-\d{4}",
            "이메일": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "고객정보블록": r"\[고객정보\]",
        }
        # 2. 프롬프트 인젝션 및 시스템 기밀 탈취 키워드
        self.injection_keywords = [
            "ignore previous instructions",
            "시스템 프롬프트",
            "탈옥",
            "jailbreak",
            "system prompt",
        ]
        # 3. 개발자 에러 및 내부 경로 패턴
        self.error_patterns = [
            r"traceback",
            r"stacktrace",
            r"exception",
            r"db_error",
            r"psycopg2",
            r"internal server error",
        ]

    def analyze_log_full(self, log_data: dict) -> dict:
        violations = []
        policy_mappings = []

        user_prompt = log_data.get("user_prompt", "") or ""
        target_url = log_data.get("target_url", "") or ""
        rag_context = log_data.get("rag_context", "") or ""
        llm_response = log_data.get("llm_response", "") or ""
        error_detail = log_data.get("error_detail", "") or ""
        security_signals = log_data.get("security_signals", {}) or {}

        # --- 규칙 A: 망분리 및 외부 전송 통제 ---
        is_external = target_url and not any(
            x in target_url for x in ["localhost", "127.0.0.1", "local://", "internal"]
        )
        if is_external or "evil.example.com" in user_prompt:
            violations.append("망분리 환경 외부 비승인 통신 시도 (SSRF 위험)")
            policy_mappings.append("전자금융감독규정 제15조 (외부통신망 분리·차단)")

        # --- 규칙 B: 민감정보 외부 유출 탐지 ---
        combined_text = f"{user_prompt} {rag_context}"
        has_pii = any(
            re.search(pattern, combined_text, re.IGNORECASE)
            for pattern in self.pii_patterns.values()
        )
        if has_pii and is_external:
            violations.append("고유식별정보 및 개인신용정보 외부 평문 유출 적발")
            policy_mappings.append("개인정보보호법 제17조 (동의 없는 제3자 제공)")

        # --- 규칙 C: 프롬프트 인젝션 및 탈옥 시도 탐지 (06번) ---
        if any(kw in user_prompt.lower() for kw in self.injection_keywords):
            violations.append("적대적 프롬프트 인젝션 및 시스템 권한 우회 시도 탐지")
            policy_mappings.append(
                "금융분야 생성형 AI 보안평가 항목 - 적대적 공격 방어"
            )

        # --- 규칙 D: 오류 및 내부 정보 노출 진단) ---
        combined_response = f"{llm_response} {error_detail}"
        if (
            any(
                re.search(pat, combined_response, re.IGNORECASE)
                for pat in self.error_patterns
            )
            or "C:\\Users" in combined_response
        ):
            violations.append("시스템 내부 에러 스택트레이스 및 내부 서버 경로 노출")
            policy_mappings.append(
                "ISMS-P 2.10.4 (오류 메시지 통제 및 민감정보 노출 방지)"
            )

        # --- 규칙 E: 데이터베이스 저장 및 계정 통제 진단---
        if security_signals and security_signals.get("password_storage") == "plaintext":
            violations.append(
                "내부 시스템 인증정보(비밀번호) 평문 저장 및 로그 기록 위반"
            )
            policy_mappings.append(
                "ISMS-P 2.7.1 (암호화 적용) / 전자금융감독규정 제27조"
            )

        # --- 규칙 F: RAG 권한 오남용 및 비인가 기능 호출 ---
        if (
            "[고객정보]" in rag_context
            and "testuser" not in user_prompt
            and log_data.get("event_type") == "chat"
        ):
            # 요청한 컨텍스트와 유저 매칭이 의심되는 경우 수평적 인가 우회로 진단
            violations.append("RAG 기반 비인가 타인 자산/고객 데이터 조회 정황 (IDOR)")
            policy_mappings.append("ISMS-P 2.6.3 (권한 부여 및 인가 검증)")

        return {
            "is_violation": len(violations) > 0,
            "violations": violations,
            "policy_mappings": policy_mappings,
        }


engine = ComplianceRuleEngine()


@app.get("/api/audit/results")
async def get_audit_results():
    audit_reports = []
    try:
        with open("tests/chatbot.jsonl", "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                log_data = json.loads(line)
                result = engine.analyze_log_full(log_data)

                # 모든 로그의 분석 결과를 웹에 던져서, 프론트엔드가 '정상/위반' 필터를 걸 수 있게 구성
                audit_reports.append(
                    {
                        "log_index": idx,
                        "event_type": log_data.get("event_type"),
                        "user_prompt": log_data.get("user_prompt"),
                        "target_url": log_data.get("target_url"),
                        "is_violation": result["is_violation"],
                        "violations": result["violations"],
                        "policy_mappings": result["policy_mappings"],
                    }
                )
        return {
            "status": "success",
            "total_logs": len(audit_reports),
            "data": audit_reports,
        }
    except FileNotFoundError:
        return {"status": "error", "message": "로그 파일을 찾을 수 없습니다."}


# --- MCP 통신용 스키마 정의 ---
class CallToolRequest(BaseModel):
    name: str
    arguments: Dict[str, Any]


class ToolResponseContent(BaseModel):
    type: str = "text"
    text: str


class MCPToolResponse(BaseModel):
    content: List[ToolResponseContent]
    is_error: bool = False


# --- MCP 엔드포인트 라우팅 ---
@app.get("/tools")
async def list_tools():
    """MCP Tools 스펙 명세 반환"""
    return {
        "tools": [
            {
                "name": "audit_compliance",
                "description": "아웃바운드 트래픽 및 데이터 유출 패턴 분석 기반 금융 보안 정책 통제 도구",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "user_input": {
                            "type": "string",
                            "description": "user text message",
                        },
                        "target_url": {
                            "type": "string",
                            "description": "outbound destination url",
                        },
                    },
                    "required": ["user_input"],
                },
            }
        ]
    }


@app.post("/tools/call", response_model=MCPToolResponse)
async def call_tool(request: CallToolRequest):
    """보안 규제 진단 룰 엔진 실행 및 MCP 규격 결과 응답"""
    if request.name != "audit_compliance":
        raise HTTPException(
            status_code=404, detail="요청된 MCP 도구를 식별할 수 없습니다."
        )

    user_input = request.arguments.get("user_input", "")
    target_url = request.arguments.get("target_url", "")

    analysis_result = engine.analyze_payload(user_input, target_url)

    return MCPToolResponse(
        content=[
            ToolResponseContent(text=json.dumps(analysis_result, ensure_ascii=False))
        ]
    )
