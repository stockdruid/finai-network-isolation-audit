from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import re
import json

app = FastAPI(title="Financial-Security-Compliance-Engine", version="1.0.0")


class ComplianceRuleEngine:
    def __init__(self):
        self.pii_patterns = {
            "전화번호": r"010-\d{4}-\d{4}",
            "이메일": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
            "고객정보블록": r"\[고객정보\]",
        }

    def analyze_log(self, user_prompt: str, target_url: str, rag_context: str) -> dict:
        violations = []
        policy_mappings = []

        is_external = target_url and not any(
            x in target_url for x in ["localhost", "127.0.0.1", "local://", "internal"]
        )

        if is_external or (user_prompt and "evil.example.com" in user_prompt):
            violations.append("망분리 환경 외부 비승인 통신 시도")
            policy_mappings.append(
                "전자금융감독규정 제15조 제1항 제3호 (외부통신망 분리·차단)"
            )

        has_pii = False
        detected_types = []

        combined_text = f"{user_prompt or ''} {rag_context or ''}"
        for name, pattern in self.pii_patterns.items():
            if re.search(pattern, combined_text):
                has_pii = True
                detected_types.append(name)

        if has_pii and is_external:
            violations.append(
                f"고유식별정보 및 개인신용정보({', '.join(detected_types)}) 외부 평문 유출 적발"
            )
            policy_mappings.append("개인정보보호법 제17조 제1항 (동의 없는 제3자 제공)")

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

                user_prompt = log_data.get("user_prompt")
                target_url = log_data.get("target_url")
                rag_context = log_data.get("rag_context")

                result = engine.analyze_log(user_prompt, target_url, rag_context)

                if result["is_violation"]:
                    audit_reports.append(
                        {
                            "log_index": idx,
                            "user_prompt": user_prompt,
                            "target_url": target_url,
                            "violations": result["violations"],
                            "policy_mappings": result["policy_mappings"],
                        }
                    )

        return {
            "status": "success",
            "total_violations": len(audit_reports),
            "data": audit_reports,
        }

    except FileNotFoundError:
        return {
            "status": "error",
            "message": "로그 파일을 찾을 수 없습니다. 경로를 확인해주세요.",
        }


rule_engine = ComplianceRuleEngine()


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

    analysis_result = rule_engine.analyze_payload(user_input, target_url)

    return MCPToolResponse(
        content=[
            ToolResponseContent(text=json.dumps(analysis_result, ensure_ascii=False))
        ]
    )
