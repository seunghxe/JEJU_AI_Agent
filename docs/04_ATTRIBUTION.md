# AI·모델·외부 자료 사용 내역

## AI 사용

| 구분 | 도구/모델 | 범위 |
|---|---|---|
| 런타임 언어모델 | Google Gemini; 제출 설정 GEMINI_MODEL=gemini-3.5-flash-lite | 사용자 조건 JSON 구조화·계산 사실 기반 설명 |
| 대체 모델 목록 | gemini-2.5-flash-lite / gemini-2.5-flash / gemini-2.0-flash | 코드상 후보; 현재 계정 이용 가능성을 보증하지 않음 |
| 개발 보조 | ChatGPT / Codex | 기획·코드·테스트·UI 조정·문서 작성 지원 |
| 이번 패키지 검증 | API 키 없는 규칙 모드 및 모의응답 | 실 Gemini 호출/유료 API 비용 없음 |

실제 선택된 런타임 모델은 연결 상태와 `llm_agent.STATE`에 기록됩니다. 설정 모델을 사용할 수 없는 경우 코드에 정의된 후보 모델로 재시도하며, 모든 호출이 실패하면 규칙 기반 해석과 정형 문장으로 전환합니다.

## 팀 수행 범위

팀은 선행 충전망 분석의 Plan B 구조, 상태데이터 품질·실질공급, 관광수요, 생활수요·통합표 구축을 분담했습니다. 이번 Agent 단계에서는 자연어 입력, 상태관리, 추천 로직, 외부 API 연동, UI, 검증과 배포 문서를 공동으로 통합했습니다. ChatGPT·Codex는 코드 작성·점검·문서 정리에 활용했으며 최종 판단과 제출 책임은 참가팀에 있습니다.

## 프레임워크·오픈소스

FastAPI(HTTP API), Uvicorn(ASGI 서버), Pydantic(요청 검증), pandas/numpy(표 계산), requests/httpx(HTTP), python-dotenv(설정), google-genai(Gemini SDK), LangGraph(상태·체크포인트), pytest(테스트), Leaflet(지도)을 사용합니다. Python 표준 라이브러리와 브라우저 기본 API도 사용합니다. RAG·벡터 검색·파인튜닝은 없습니다.

전체 설치 버전은 requirements-tested.txt, 설치된 메타데이터의 라이선스·프로젝트 링크는 docs/dependency_inventory.json을 참고합니다. 메타데이터 빈 값은 허가 불필요를 의미하지 않습니다. Leaflet 라이선스 원문은 static/leaflet/LICENSE.txt에 보존했습니다. 프로젝트 자체에 임의로 MIT 등 재배포 라이선스를 부여하지 않았습니다. 대회 소유권 조건과 팀의 권한을 확인해야 합니다.

공식 프로젝트: https://fastapi.tiangolo.com/ , https://www.uvicorn.org/ , https://docs.pydantic.dev/ , https://pandas.pydata.org/ , https://github.com/langchain-ai/langgraph , https://github.com/googleapis/python-genai , https://leafletjs.com/ .

## 지도·이미지

기본 지도는 OpenStreetMap 타일(https://tile.openstreetmap.org/)과 Leaflet입니다. 화면 attribution을 유지합니다. 지도 데이터·타일은 제공처 정책(https://www.openstreetmap.org/copyright , https://operations.osmfoundation.org/policies/tiles/)을 따릅니다. 타일 대량 다운로드·동봉은 하지 않았습니다. 카카오 지도·경로·검색은 제공처 약관에 따릅니다.

차량 사진은 외부 Wikimedia Commons를 직접 읽으며 ZIP에 이미지 사본을 넣지 않았습니다. 화면과 아래 표에 원문 파일·저작자·라이선스 정보를 표시하며, 외부 파일은 해당 원문 페이지의 최신 조건을 따릅니다.

| 차량 | 원문 파일 | 코드상 저작자 |
|---|---|---|
| 코나 일렉트릭 | https://commons.wikimedia.org/wiki/File:0_Hyundai_Kona_Electric_(OS)_0.jpg | Benespit |
| 아이오닉 5 | https://commons.wikimedia.org/wiki/File:0_Hyundai_Ioniq_5.jpg | Benespit |
| 니로 EV | https://commons.wikimedia.org/wiki/File:0_Kia_Niro_EV_(SG2)_1.jpg | Benespit |
| EV6 | https://commons.wikimedia.org/wiki/File:0_Kia_EV6_0.jpg | Benespit |
| 모델 3 | https://commons.wikimedia.org/wiki/File:Tesla_Model_3_Front_View.jpg | Ominae |
| 조에 | https://commons.wikimedia.org/wiki/File:White_Renault_Zoe_(front).jpg | Fiver, der Hellseher |

브랜드/차량명은 식별 목적이며 해당 제조사의 공식 서비스나 제휴를 의미하지 않습니다. 헤더 일러스트와 아이콘은 제출 코드의 HTML/CSS/SVG 구성요소로 포함되어 있습니다.

## 외부 데이터

DATA_USAGE.md 참조. 제주데이터허브·환경공단·카카오·공공데이터포털 월별 충전 이력은 서로 다른 출처입니다. 데이터를 모두 제주데이터허브로 묶어 기재하지 않습니다. 원시 개인정보는 포함하지 않으며, 평가용 키는 운영진 안내에 따라 비공개 제출 ZIP의 `.env`에만 포함하고 공개 GitHub·보고서·영상에는 노출하지 않습니다.
