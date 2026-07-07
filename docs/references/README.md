# 컴플라이언스 원천 자료

팀원 합의 근거 자료. 매핑표·평가기준 안내서·챗봇 실 로그 원본.

## 자료 목록

| 파일 | 유형 | 출처/용도 |
|------|------|-----------|
| `chatbot_sample_logs.jsonl` | 실 로그 (16건) | 개발자 A 챗봇 파이프라인 실행 결과. `scripts/import_chatbot_logs.py`로 chatbot_logs 테이블에 적재. |
| `금융_AI_통합_인증_매핑표_프로젝트적용_정제본.xlsx` | 매핑표 (핵심) | 정책팀 산출. 공통통제 25 + Detector 12 + 요구사항 268. `scripts/import_compliance_mappings.py`가 파싱. |
| `개인정보_위험도_산정체계.xlsx` | 위험도 산정 (v4) | 정책팀 2026-07-07. PII 유형별 위험도 점수 15개 + 등급 기준. `scripts/import_pii_risk.py`. |
| `금융권_적합_ISMS-P_법령_매핑.xlsx` | 인증기준 (v4) | 정책팀 2026-07-07. 금융권 선정 48 인증기준 + 191 세부 점검항목 + 법령·제재. `scripts/import_isms_p.py`. |
| `법령_매핑.xlsx` | 매핑 참조 | 챗봇 서비스 법령 기반 점검표 (자동진단 21 + 수동점검 19). |
| `금융권_적합_ISMS-P_보조기준_매핑.xlsx` | 매핑 참조 | ISMS-P 인증기준 192개 정밀 매핑 (이전 버전). |
| `[첨부2] (금융보안원) 혁신금융서비스 관련 안전성 평가 항목표.xlsx` | 평가 항목 | 혁신금융서비스 승인용 안전성 평가 8개 영역. |
| `2026년도 전자금융기반시설 보안 취약점 평가기준(제2026-1호).xlsx` | 평가 기준 | 서버/WAS/DB/네트워크/OS/컨테이너 등 인프라 취약점 평가기준. |
| `생성형 AI 연계 이용 보안대책 평가 절차 안내.pdf` | 절차 안내 | 금융보안원. 생성형 AI 연계 시 보안대책 평가 절차. |
| `aaS 및 생성형 AI 모델 서비스 제공자 평가 안내.pdf` | 절차 안내 | 금융보안원. SaaS/PaaS + 생성형 AI 모델 서비스 제공자 평가 안내. |
| `전자금융기반시설 보안 취약점 평가기준 안내서(제2026-1호).pdf` | 규정 안내서 | 전자금융기반시설 취약점 평가 상세 안내 (64쪽). |

## 매핑표 시트 구조

`금융_AI_통합_인증_매핑표_프로젝트적용_정제본.xlsx`의 주요 시트:

| 시트 | 내용 | DB 적재 |
|------|------|---------|
| `01_공통통제_마스터` | GOV/DATA/MODEL/OPS/INFRA 25개 공통통제 | `common_controls` |
| `18_MVP12_자동화명세` | 12개 Detector 명세 (챗봇/시스템/데이터) | `detectors` |
| `22_프로젝트적용_통합` | 원천기준 → 공통통제 매핑 268건 | `requirements` |
| `05~08_ISMS-P_*` | ISMS-P 101 인증기준 + 정밀 매핑 + 확인질문 | (미적재, 향후) |
| `10_생성형AI_평가20` | 금융보안원 생성형 AI 평가기준 20개 | (26 시트에 흡수) |
| `11_AI보안가이드30` | 국가·공공기관 AI 보안대책 30개 | (26 시트에 흡수) |
| `20_YAML_예시` | Detector YAML 실행 예시 | (수동 참조) |

## 재적재 명령

```bash
# 매핑표 XLSX → DB (v3)
python scripts/import_compliance_mappings.py

# 챗봇 실 로그 JSONL → DB (기존 로그 대체)
python scripts/import_chatbot_logs.py --reset

# 개인정보 위험도 산정체계 XLSX → DB (v4)
python scripts/import_pii_risk.py

# 금융권 ISMS-P 법령 매핑 XLSX → DB (v4)
python scripts/import_isms_p.py
```
