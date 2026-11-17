# Prompt·Tool/API·상태관리 명세

## Prompt 위치

`llm_agent.py:parse_with_gemini`는 질문을 place, origin, intent, preference, battery JSON으로 변환하도록 요청합니다. `summarize_with_gemini`는 계산된 facts JSON만 근거로 한국어 2~3문장을 만들고 없는 수치를 생성하지 않도록 요청합니다. 프롬프트 원문은 해당 파일에 포함되어 있습니다.

parse 프롬프트의 preference에는 이전 버전 명칭이 남아 있지만 현재 AgentService는 UI/ConversationGraph에서 받은 4개 기준을 실제 정렬 기준으로 사용합니다. 이 패키징 작업에서는 추천 동작을 바꾸지 않았습니다. 보고서에 LLM이 모든 추천 가중치를 자율 생성한다고 기재하면 안 됩니다.

## 도구별 입력·출력·호출 조건

| 구현 | 입력 | 출력 | 호출 |
|---|---|---|---|
| Gemini 해석 | 사용자 질문 | 구조화 조건 | 키 있을 때; 실패 시 규칙 |
| Kakao Local | 추출한 장소명 | 명칭·주소·좌표 | 키 설정·내장/상호 검색 필요 |
| Kakao Mobility | 출발·도착 좌표 | 분·km·도로 폴리라인 | 후보/선정 시설 경로 조회 |
| 환경공단 상태 | 인증키·페이지 | 충전기 상태 집계 | 실시간 키 설정; 5분 캐시 |
| 제주데이터허브 API | 데이터 코드·프로젝트 키·기간·페이지 | 이력/방문수요 집계 | API 설정 시 백그라운드 또는 점검 |
| 허브 저장 자료 로더 | hub_snapshot.json·시설 카탈로그 해시 | 검증된 과거 집계 4종 | auto 무키 또는 snapshot 모드, 외부 호출 없음 |
| agent_core | 시설표·조건 | 후보·기본 점수·경고 | 요청마다 |
| station_context | 시설·요일·지역 | 위험·근거·출처·보정 | 후보 평가·카드 작성 |
| Gemini 요약 | 계산 facts | 설명 문자열 | 키 설정; 실패 시 정형 문장 |

## HTTP 인터페이스

| 경로 | 메서드 | 용도 |
|---|---|---|
| / | GET | 사용자 화면 |
| /api/meta | GET | 차량·기준·연결 요약 |
| /api/stations | GET | 지도 시설 목록 |
| /api/status | GET | 상세 연결 상태 |
| /api/ask | POST | 추천·후속 요청 |
| /api/progress/{progress_id} | GET | 현재 요청 단계 |
| /api/conversation/{thread_id} | DELETE | 세션 초기화 |
| /api/live/refresh | POST | 실시간 상태 재조회 |
| /api/datahub/refresh | POST | 모드에 따른 허브 API/캐시 점검 또는 동봉 집계 재검증 |
| /api/live/station/{facility_id} | GET | 특정 시설 상태 |
| /api/planb/recheck | POST | B 재확인 |
| /api/gemini/check | POST | 짧은 실제 모델 호출 |

AskRequest는 최대 2,000자 질문, 배터리 1~100, 차량·규격·출발지·선호·thread_id 등을 받습니다. 같은 thread_id로 목적지·배터리·제외 시설·최근 4턴 기록을 이어갑니다. 메모리는 프로세스 내부이며 운영 배포는 workers 1을 사용합니다. 사용자 인증·영속 세션·멀티 프로세스 공유는 구현하지 않았습니다.

## 신뢰성·비용

API 실패를 현재 상태와 구분하고 규칙/과거 자료로 대체합니다. 허브는 중복 페이지와 미완료 수집을 제외하며 오류 문구에 키 URL을 넣지 않습니다. 모든 출처가 확인되었다거나 LLM 환각이 불가능하다고 주장하지 않습니다. 외부 키·데이터 권한은 평가자가 준비할 수 있도록 매뉴얼에 기록하고, 평가용 AI 키 예외는 대회 규정 범위 내에서만 처리합니다.
