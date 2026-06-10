"""시드 데이터 — 개발/데모용 더미 로그 + 진단 + 정책 + 점수 생성.

Usage:
    python scripts/seed_data.py          # 기본 30개 로그
    python scripts/seed_data.py --count 100
    python scripts/seed_data.py --reset   # 기존 데이터 삭제 후 재생성
"""
from __future__ import annotations

import argparse
import asyncio
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

# 프로젝트 루트를 path에 추가
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.models import ChatbotLog, ComplianceScore, DiagnosisResult, PolicyMapping
from db.session import SessionLocal, engine

# ---------------------------------------------------------------------------
# 시드 상수
# ---------------------------------------------------------------------------

KST = timezone(timedelta(hours=9))

INTERNAL_QUERIES = [
    "예금 상품 추천해줘",
    "적금 금리 비교해줘",
    "대출 한도 조회",
    "신용카드 혜택 알려줘",
    "펀드 수익률 비교",
    "보험 상품 추천",
    "연금저축 가입 방법",
    "환율 조회해줘",
    "주식 시세 알려줘",
    "ISA 계좌 개설 방법",
]

EXTERNAL_QUERIES = [
    "외부 API로 금리 전망 분석해줘",
    "해외 시장 데이터 조회",
    "외부 LLM으로 리스크 분석",
    "글로벌 경제 지표 요약",
    "외부 신용평가 조회",
]

INTERNAL_RESPONSES = [
    "정기예금 상위 3개 상품: KB국민 3.5%, 신한 3.4%, 우리 3.3%",
    "적금 금리 비교 결과를 안내드립니다...",
    "대출 한도 조회 결과: 최대 5,000만원",
    "신용카드 혜택: 포인트 적립 1.5%, 할인 0.5%",
    "펀드 수익률 TOP 3: 삼성 KODEX 12.3%, 미래에셋 11.8%...",
    "종합보험 상품 추천: 삼성생명 무배당 종합보험...",
    "연금저축 가입: 은행/증권사 방문 또는 온라인 가입 가능",
    "오늘의 환율: USD 1,320원, EUR 1,430원, JPY 880원",
    "삼성전자 현재가 72,000원, 전일대비 +1.2%",
    "ISA 계좌 개설: 1인 1계좌, 연 2,000만원 납입한도",
]

EXTERNAL_RESPONSES = [
    "GPT-4 분석 결과: 하반기 금리 인하 전망 우세...",
    "Bloomberg API 조회: S&P 500 +0.8%, NASDAQ +1.2%",
    "외부 LLM 리스크 분석: 포트폴리오 VaR 2.3%",
    "글로벌 GDP 성장률 전망: 미국 2.1%, 유로존 0.8%",
    "외부 신용평가 조회 완료: A+ 등급",
]

VIOLATION_TYPES = [
    "external_llm_call",
    "unauthorized_data_egress",
    "pii_leak_detected",
    "unencrypted_transmission",
    "policy_bypass_attempt",
]

SEVERITIES = ["critical", "high", "medium", "low", "info"]
SEVERITY_WEIGHTS = [0.05, 0.15, 0.35, 0.30, 0.15]

POLICY_SEEDS = [
    ("망분리", "NS-001", "내부망-외부망 분리", "금융회사 내부 업무망과 인터넷망의 물리적/논리적 분리 요구"),
    ("망분리", "NS-002", "외부 통신 통제", "외부 네트워크 통신 시 승인된 경로만 허용"),
    ("망분리", "NS-003", "데이터 이동 통제", "망간 데이터 전송 시 보안 검증 필수"),
    ("접근통제", "AC-001", "접근 권한 관리", "최소 권한 원칙에 따른 시스템 접근 권한 부여"),
    ("접근통제", "AC-002", "인증 및 식별", "다단계 인증 등 강화된 사용자 인증 체계 운영"),
    ("데이터보호", "DP-001", "개인정보 암호화", "개인정보 및 금융정보 저장/전송 시 암호화 필수"),
    ("데이터보호", "DP-002", "데이터 유출 방지", "DLP 솔루션 등을 통한 정보 유출 모니터링"),
    ("AI거버넌스", "AG-001", "AI 모델 투명성", "AI 모델 판단 근거의 설명 가능성 확보"),
    ("AI거버넌스", "AG-002", "외부 AI 서비스 사용 통제", "외부 AI API 호출 시 데이터 전송 범위 제한"),
    ("AI거버넌스", "AG-003", "AI 편향성 모니터링", "AI 모델 출력에 대한 편향성 정기 점검"),
    ("감사추적", "AT-001", "로그 보관", "전자금융거래 관련 로그 5년 이상 보관"),
    ("감사추적", "AT-002", "접근 기록 관리", "시스템 접근 및 조작 기록의 위변조 방지"),
]

REGULATIONS = [
    {"law": "전자금융거래법", "section": "21조"},
    {"law": "전자금융감독규정", "section": "15조"},
    {"law": "금융분야 클라우드 이용 가이드", "section": "3.2"},
    {"law": "개인정보보호법", "section": "29조"},
    {"law": "신용정보법", "section": "40조"},
    {"law": "금융위원회 AI 가이드라인", "section": "4.1"},
]

TARGET_URLS = [
    "api.openai-mock.example.com",
    "llm-proxy.external.example.com",
    "api.bloomberg-mock.example.com",
    "credit-score.external.example.com",
]

VULN_TAGS = [None, None, None, "EV-001", "EV-002", "EV-003"]


# ---------------------------------------------------------------------------
# 생성 함수
# ---------------------------------------------------------------------------

def _rand_ts(days_back: int = 14) -> datetime:
    now = datetime.now(KST)
    delta = timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(8, 18),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59),
    )
    return now - delta


def _make_log(i: int) -> dict:
    is_external = random.random() < 0.3
    mode = "external" if is_external else "internal"
    vuln_tag = random.choice(VULN_TAGS) if is_external else None

    return {
        "created_at": _rand_ts(),
        "request_id": uuid.uuid4(),
        "mode": mode,
        "user_input": random.choice(EXTERNAL_QUERIES if is_external else INTERNAL_QUERIES),
        "bot_response": random.choice(EXTERNAL_RESPONSES if is_external else INTERNAL_RESPONSES),
        "model_name": "gpt-4-mock" if is_external else "qwen2.5:7b",
        "response_time_ms": random.randint(200, 3000) if is_external else random.randint(100, 1500),
        "target_url": random.choice(TARGET_URLS) if is_external else None,
        "intentional_vuln_tag": vuln_tag,
        "guardrail_triggered": [],
        "flagged": is_external and random.random() < 0.4,
    }


def _make_diagnosis(log_id: int, log_mode: str, log_vuln_tag: str | None) -> dict | None:
    # external 모드만 진단 대상, 일부 internal도 false positive로 포함
    if log_mode == "internal" and random.random() > 0.05:
        return None

    severity = random.choices(SEVERITIES, weights=SEVERITY_WEIGHTS, k=1)[0]
    correct = log_vuln_tag is not None if log_mode == "external" else False

    return {
        "source_log_id": log_id,
        "violation_type": random.choice(VIOLATION_TYPES),
        "severity": severity,
        "matched_target_url": random.choice(TARGET_URLS) if log_mode == "external" else None,
        "regulation_reference": random.choice(REGULATIONS),
        "correct": correct,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def seed(count: int, reset: bool) -> None:
    async with SessionLocal() as session:
        if reset:
            await session.execute(delete(DiagnosisResult))
            await session.execute(delete(ComplianceScore))
            await session.execute(delete(ChatbotLog))
            await session.execute(delete(PolicyMapping))
            await session.commit()
            # 시퀀스 리셋
            for tbl in ["chatbot_logs", "diagnosis_results", "policy_mappings", "compliance_scores"]:
                await session.execute(text(f"ALTER SEQUENCE {tbl}_id_seq RESTART WITH 1"))
            await session.commit()
            print("[reset] 기존 데이터 삭제 완료")

        # 1) 정책 매핑
        existing = await session.execute(text("SELECT count(*) FROM policy_mappings"))
        if existing.scalar() == 0:
            for cat, code, title, desc in POLICY_SEEDS:
                session.add(PolicyMapping(
                    category=cat, code=code, title=title, description=desc,
                    severity_weight=round(random.uniform(3.0, 9.0), 1),
                    related_rules=[random.choice(REGULATIONS)],
                ))
            await session.commit()
            print(f"[seed] policy_mappings {len(POLICY_SEEDS)}건 생성")

        # 2) 챗봇 로그
        logs_created = []
        for i in range(count):
            data = _make_log(i)
            log = ChatbotLog(**data)
            session.add(log)
            await session.flush()
            logs_created.append((log.id, data["mode"], data["intentional_vuln_tag"]))
        await session.commit()
        print(f"[seed] chatbot_logs {count}건 생성")

        # 3) 진단 결과
        diag_count = 0
        for log_id, mode, vuln_tag in logs_created:
            d = _make_diagnosis(log_id, mode, vuln_tag)
            if d:
                session.add(DiagnosisResult(**d))
                diag_count += 1
        await session.commit()
        print(f"[seed] diagnosis_results {diag_count}건 생성")

        # 4) 컴플라이언스 점수
        passed = diag_count - int(diag_count * 0.3)
        failed = int(diag_count * 0.2)
        warnings = diag_count - passed - failed
        score = ComplianceScore(
            scan_id=f"scan-{datetime.now(KST).strftime('%Y%m%d-%H%M')}",
            total_score=round(random.uniform(60.0, 95.0), 2),
            passed=passed,
            failed=failed,
            warnings=max(warnings, 0),
            details={"generated": True, "seed_count": count},
        )
        session.add(score)
        await session.commit()
        print(f"[seed] compliance_scores 1건 생성 (score={score.total_score})")

    await engine.dispose()
    print("[done] 시드 데이터 생성 완료")


def main() -> None:
    parser = argparse.ArgumentParser(description="시드 데이터 생성")
    parser.add_argument("--count", type=int, default=30, help="생성할 로그 수")
    parser.add_argument("--reset", action="store_true", help="기존 데이터 삭제 후 재생성")
    args = parser.parse_args()
    asyncio.run(seed(args.count, args.reset))


if __name__ == "__main__":
    main()
