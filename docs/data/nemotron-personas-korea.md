# Nemotron-Personas-Korea — 검토 결과 (2026-06-05)

> 멘토 추천 데이터셋. 합성 한국어 페르소나 100만 건. 금융 챗봇 테스트/시나리오 데이터의 시드로 활용.

- **소스**: <https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea>
- **로딩**: `datasets.load_dataset('nvidia/Nemotron-Personas-Korea', split='train', streaming=True)`
- **크기**: train 1,000,000 rows
- **언어**: 한국어 (페르소나 본문 풍부), 인구통계 카테고리는 한국 사회 기준
- **라이선스**: HF 페이지에서 별도 확인 필요 (현재 metadata에 명시 없음)

## 컬럼 (26개)

| 컬럼 | 타입 | 비고 |
|------|------|------|
| `uuid` | str | 고유 ID |
| `persona` | str | 한 문장 요약 페르소나 |
| `professional_persona` | str | 직장에서의 모습 |
| `sports_persona` | str | 운동/취미 |
| `arts_persona` | str | 예술/문화 |
| `travel_persona` | str | 여행 스타일 |
| `culinary_persona` | str | 음식 취향 |
| `family_persona` | str | 가족 관계 |
| `cultural_background` | str | 문화 배경 |
| `skills_and_expertise` | str | 전문성 본문 |
| `skills_and_expertise_list` | str (JSON 배열 직렬화) | 스킬 목록 |
| `hobbies_and_interests` | str | 취미 본문 |
| `hobbies_and_interests_list` | str (JSON 배열 직렬화) | 취미 목록 |
| `career_goals_and_ambitions` | str | 커리어 목표 |
| `sex` | str | `남자` / `여자` |
| `age` | int | 만 나이 |
| `marital_status` | str | 결혼 상태 |
| `military_status` | str | 군 복무 상태 |
| `family_type` | str | 가구 형태 |
| `housing_type` | str | 주거 형태 |
| `education_level` | str | 최종 학력 |
| `bachelors_field` | str | 학사 전공 (해당없음 포함) |
| `occupation` | str | 직업 |
| `district` | str | 시군구 |
| `province` | str | 시도 |
| `country` | str | `대한민국` |

## 샘플 (10명, 다양성 확인)

| 나이 | 성별 | 시도 | 직업 |
|------|------|------|------|
| 74 | 남 | 광주 | 하역 및 적재 관련 단순 종사원 |
| 71 | 여 | 서울 | 회계 사무원 |
| 73 | 남 | 서울 | 무직 |
| 46 | 여 | 경기 | 무직 |
| 50 | 여 | 부산 | 그 외 서비스 관련 단순 종사원 |
| 33 | 여 | 인천 | 경리 사무원 |
| 31 | 남 | 경상북 | 강구조물 가공원 |
| 76 | 남 | 서울 | 무직 |
| 44 | 남 | 강원 | 전화 상담원 |
| 27 | 남 | 경기 | 무직 |

→ 연령 27~76, 직업/지역 다양. 소득 추정 어려운 페르소나 (무직, 단순 종사원) 다수 포함.

## 프로젝트 활용 시나리오

### 1. RAG 시드는 아님

- 페르소나는 **사용자 측 시뮬레이션** 데이터. 금융 상품 정보 (`finlife`, `ECOS`)와 역할이 다름.
- Chroma에 적재 X. 대신 **챗봇 입력 시나리오 생성** 용도.

### 2. 의도적 위반 시나리오 (`intentional_vuln_tag`) 시드

페르소나 기반으로 의도적 PII 누출 케이스 생성:

| vuln_tag | 시나리오 | 페르소나 활용 |
|----------|----------|-----------------|
| `EV-001` | "외부 LLM에 분석 맡겨줘" 유도 | 직업/취미 텍스트를 prompt 일부로 사용 |
| `EV-002` | 주민번호 포함 입력 | 페르소나 + 가짜 SSN (`{age}1234-1{생성}`) 조합 |
| `EV-003` | 카드번호 포함 입력 | 페르소나 + 가짜 16자리 카드번호 |
| `EV-004` | 가족 정보 노출 유도 | `family_persona` 활용 |

### 3. 가상 고객 프로필 생성

`scripts/seed_customers.py`(신규)에서 N명 샘플링 → 가상 계좌/거래 데이터와 join.

- 페르소나의 `occupation`/`age`/`housing_type` → 가상 소득/자산 추정 룰
- `family_persona` → 부양가족 수 도출
- `province` → 지역별 영업점 매핑

### 4. 챗봇 E2E 테스트 케이스

페르소나별로 typical 질문 자동 생성:

- 70대 무직 → "노후 연금 추천", "고정금리 예금 어디가 좋아"
- 30대 사무원 → "주택청약", "신용카드 비교"
- 자영업 페르소나 → "사업자 대출 한도"

## 변환/사용 주의사항

### 데이터 품질
- `skills_and_expertise_list` / `hobbies_and_interests_list` 는 **문자열로 직렬화된 Python list**. `ast.literal_eval` 필요.
- 모든 필드 한국어. 영어 매핑 필요 시 별도 번역.

### 라이선스
- HF metadata에 license 비어있음 → **사용 전 NVIDIA 페이지 라이선스 약관 직접 확인 필수**.
- 발표/배포 자료에 출처 명시 (`nvidia/Nemotron-Personas-Korea`).

### 100만 row 전체 다운로드 비권장
- 약 수 GB로 추정. 로컬 디스크 압박.
- **streaming 모드 + 필요 분량만 sampling** 권장 (10~10,000 rows).

### Windows symlink 경고
- HF 캐시가 심볼릭 링크 사용. Windows 일반 권한에서는 disable 됨 (디스크 더 씀, 동작은 정상).
- 무시 가능. 또는 `HF_HUB_DISABLE_SYMLINKS_WARNING=1` env.

## 다음 액션

- [ ] **`scripts/sample_personas.py`** — N명 샘플링 + JSON 저장 (별도 PR)
- [ ] 개발자 A와 `intentional_vuln_tag` 코드 체계 (`EV-001` etc) 합의 — 본 문서 표 활용
- [ ] 가상 고객 데이터 스키마 설계 (페르소나 + 계좌 + 거래)
- [ ] HF 라이선스 확인 → 사용 가능 여부 결정 → 결정 시 본 문서 갱신

## Related

- `scripts/sample_personas.py` (생성 예정)
- 프로젝트 메인: vault `금융 AI 망분리 컴플라이언스 진단 시스템`
- 멘토 추천 근거: vault `기획 멘토링 2026-05-30` Q5
