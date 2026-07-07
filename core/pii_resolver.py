"""PII 필드명 정규화 (챗봇 로그 원본 라벨 → `pii_types.name` 정본).

챗봇 로그의 `pii_fields`는 개발자 A가 자유롭게 붙인 라벨(영문 snake_case, 한글 축약형 등)
이라 정책팀 산정체계의 `pii_types.name`과 정확히 일치하지 않는다.

이 모듈이 정본 명칭으로 매핑한다.

- 정확 일치 (case-insensitive) 우선
- 그다음 별칭 사전(ALIASES)
- 마지막으로 부분 키워드 매칭 (contains)

매칭되지 않으면 `None` 반환 → 스코어링 시 위험도 0으로 처리 (미분류).
"""
from __future__ import annotations


CANONICAL_NAMES: list[str] = [
    "주민등록번호",
    "신용카드번호",
    "계좌번호",
    "신분증 (주민등록증/면허증)",
    "생체인식정보 (지문·홍채 등)",
    "의료정보",
    "혼인정보",
    "외국인등록번호",
    "카드 소비내역 (민감정보 가능)",
    "소득·자산정보",
    "이름",
    "전화번호",
    "이메일",
    "주소",
    "접속 IP·로그",
]


# 원본 라벨(소문자) → 정본 명칭
ALIASES: dict[str, str] = {
    # 주민등록번호
    "ssn": "주민등록번호",
    "rrn": "주민등록번호",
    "resident_id": "주민등록번호",
    "resident_number": "주민등록번호",
    "주민번호": "주민등록번호",
    # 신용카드
    "credit_card": "신용카드번호",
    "card_number": "신용카드번호",
    "cc_number": "신용카드번호",
    "카드번호": "신용카드번호",
    # 계좌
    "account": "계좌번호",
    "account_number": "계좌번호",
    "bank_account": "계좌번호",
    # 신분증
    "id_card": "신분증 (주민등록증/면허증)",
    "driver_license": "신분증 (주민등록증/면허증)",
    "license": "신분증 (주민등록증/면허증)",
    "여권번호": "신분증 (주민등록증/면허증)",
    # 생체인식
    "biometric": "생체인식정보 (지문·홍채 등)",
    "fingerprint": "생체인식정보 (지문·홍채 등)",
    "face_id": "생체인식정보 (지문·홍채 등)",
    "홍채": "생체인식정보 (지문·홍채 등)",
    "지문": "생체인식정보 (지문·홍채 등)",
    # 의료
    "medical": "의료정보",
    "health": "의료정보",
    "diagnosis": "의료정보",
    # 혼인
    "marriage": "혼인정보",
    "marital": "혼인정보",
    # 외국인등록
    "arn": "외국인등록번호",
    "alien_registration": "외국인등록번호",
    # 카드 소비내역
    "card_history": "카드 소비내역 (민감정보 가능)",
    "consumption": "카드 소비내역 (민감정보 가능)",
    "transaction_history": "카드 소비내역 (민감정보 가능)",
    "카드사용내역": "카드 소비내역 (민감정보 가능)",
    # 소득·자산
    "income": "소득·자산정보",
    "assets": "소득·자산정보",
    "salary": "소득·자산정보",
    "재산": "소득·자산정보",
    # 이름
    "name": "이름",
    "full_name": "이름",
    "customer_name": "이름",
    "user_name": "이름",
    "성함": "이름",
    # 전화번호
    "phone": "전화번호",
    "mobile": "전화번호",
    "phone_number": "전화번호",
    "tel": "전화번호",
    "핸드폰": "전화번호",
    "휴대폰": "전화번호",
    # 이메일
    "email": "이메일",
    "e_mail": "이메일",
    "mail": "이메일",
    # 주소
    "address": "주소",
    "addr": "주소",
    "home_address": "주소",
    # IP/로그
    "ip": "접속 IP·로그",
    "ip_address": "접속 IP·로그",
    "user_agent": "접속 IP·로그",
    "access_log": "접속 IP·로그",
    "session": "접속 IP·로그",
}


# 부분 키워드 매칭 (별칭에도 없는 경우 마지막 fallback)
KEYWORD_MATCHERS: list[tuple[str, str]] = [
    ("주민", "주민등록번호"),
    ("ssn", "주민등록번호"),
    ("card", "신용카드번호"),
    ("계좌", "계좌번호"),
    ("account", "계좌번호"),
    ("신분", "신분증 (주민등록증/면허증)"),
    ("의료", "의료정보"),
    ("medical", "의료정보"),
    ("phone", "전화번호"),
    ("전화", "전화번호"),
    ("email", "이메일"),
    ("이메일", "이메일"),
    ("메일", "이메일"),
    ("name", "이름"),
    ("이름", "이름"),
    ("addr", "주소"),
    ("주소", "주소"),
    ("ip", "접속 IP·로그"),
]


_CANONICAL_LOWER = {n.lower(): n for n in CANONICAL_NAMES}


def resolve(label: str | None) -> str | None:
    """단일 라벨을 정본 명칭으로 정규화. 매칭 실패 시 None."""
    if not label:
        return None
    raw = str(label).strip()
    if not raw:
        return None
    key = raw.lower()

    # 1. 정확 일치 (case-insensitive)
    if key in _CANONICAL_LOWER:
        return _CANONICAL_LOWER[key]

    # 2. 별칭 사전
    if key in ALIASES:
        return ALIASES[key]

    # 3. 부분 키워드 매칭
    for kw, canonical in KEYWORD_MATCHERS:
        if kw in key:
            return canonical

    return None


def resolve_many(labels: list[str] | None) -> list[str | None]:
    """라벨 리스트 전체 정규화. 매칭 실패도 None으로 보존 (인덱스 정렬 유지)."""
    if not labels:
        return []
    return [resolve(x) for x in labels]


def resolve_and_partition(labels: list[str] | None) -> tuple[list[str], list[str]]:
    """정규화된 정본 리스트 + 매칭 실패 원본 리스트를 분리 반환."""
    matched: list[str] = []
    unmatched: list[str] = []
    for x in labels or []:
        r = resolve(x)
        if r is None:
            unmatched.append(str(x))
        else:
            matched.append(r)
    return matched, unmatched
