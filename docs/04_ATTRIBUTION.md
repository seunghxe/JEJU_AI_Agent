# AI·모델·외부 자료 사용 내역

## AI 사용

| 구분 | 도구/모델 | 범위 |
|---|---|---|
| 런타임 언어모델 | Google Gemini; 기본 GEMINI_MODEL=gemini-2.5-flash-lite | 사용자 조건 JSON 구조화·계산 사실 기반 설명 |
| 대체 모델 목록 | gemini-2.5-flash-lite / gemini-2.5-flash / gemini-2.0-flash | 코드상 후보; 현재 계정 이용 가능성을 보증하지 않음 |
| 개발 보조 | ChatGPT / Codex | 기획·코드·테스트·UI 조정·문서 작성 지원 |
| 이번 패키지 검증 | API 키 없는 규칙 모드 및 모의응답 | 실 Gemini 호출/유료 API 비용 없음 |

실제 선택된 런타임 모델은 연결 상태와 llm_agent.STATE에 기록됩니다. 팀은 개발 시 사용한 정확한 모델명·사용기간·다른 AI 도구를 본 문서에 보완해야 합니다. 확인할 수 없는 모델 버전을 추정하여 기재하지 않았습니다. 팀원별 역할도 팀 확인 후 추가하세요.

## 프레임워크·오픈소스

FastAPI(HTTP API), Uvicorn(ASGI 서버), Pydantic(요청 검증), pandas/numpy(표 계산), requests/httpx(HTTP), python-dotenv(설정), google-genai(Gemini SDK), LangGraph(상태·체크포인트), pytest(테스트), Leaflet(지도)을 사용합니다. Python 표준 라이브러리와 브라우저 기본 API도 사용합니다. RAG·벡터 검색·파인튜닝은 없습니다.

전체 설치 버전은 requirements-tested.txt, 설치된 메타데이터의 라이선스·프로젝트 링크는 docs/dependency_inventory.json을 참고합니다. 메타데이터 빈 값은 허가 불필요를 의미하지 않습니다. Leaflet 라이선스 원문은 static/leaflet/LICENSE.txt에 보존했습니다. 프로젝트 자체에 임의로 MIT 등 재배포 라이선스를 부여하지 않았습니다. 대회 소유권 조건과 팀의 권한을 확인해야 합니다.

공식 프로젝트: https://fastapi.tiangolo.com/ , https://www.uvicorn.org/ , https://docs.pydantic.dev/ , https://pandas.pydata.org/ , https://github.com/langchain-ai/langgraph , https://github.com/googleapis/python-genai , https://leafletjs.com/ .

## 지도·이미지

기본 지도는 OpenStreetMap 타일(https://tile.openstreetmap.org/)과 Leaflet입니다. 화면 attribution을 유지합니다. 지도 데이터·타일은 제공처 정책(https://www.openstreetmap.org/copyright , https://operations.osmfoundation.org/policies/tiles/)을 따릅니다. 타일 대량 다운로드·동봉은 하지 않았습니다. 카카오 지도·경로·검색은 제공처 약관에 따릅니다.

차량 사진은 외부 Wikimedia Commons를 직접 읽으며 ZIP에 이미지 사본을 넣지 않았습니다. 원 코드가 표시하는 저작자와 라이선스(CC BY-SA 4.0)는 아래와 같습니다. 이번 작업에서 각 원문 파일의 라이선스를 재검증하지 않았으므로 공개 시 최종 확인이 필요합니다.

| 차량 | 원문 파일 | 코드상 저작자 |
|---|---|---|
| 코나 일렉트릭 | https://commons.wikimedia.org/wiki/File:0_Hyundai_Kona_Electric_(OS)_0.jpg | Benespit |
| 아이오닉 5 | https://commons.wikimedia.org/wiki/File:0_Hyundai_Ioniq_5.jpg | Benespit |
| 니로 EV | https://commons.wikimedia.org/wiki/File:0_Kia_Niro_EV_(SG2)_1.jpg | Benespit |
| EV6 | https://commons.wikimedia.org/wiki/File:0_Kia_EV6_0.jpg | Benespit |
| 모델 3 | https://commons.wikimedia.org/wiki/File:Tesla_Model_3_Front_View.jpg | Ominae |
| 조에 | https://commons.wikimedia.org/wiki/File:White_Renault_Zoe_(front).jpg | Fiver, der Hellseher |

브랜드/차량명은 식별 목적이며 해당 제조사의 공식 서비스나 제휴를 의미하지 않습니다. 기존 헤더 일러스트와 아이콘은 제공받은 HTML/CSS/JS에 포함된 요소를 유지했습니다. 별도 외부 제작물 여부는 팀이 확인해야 합니다.

## 외부 데이터

DATA_USAGE.md 참조. 제주데이터허브·환경공단·카카오·공공데이터포털 월별 충전 이력은 서로 다른 출처입니다. 데이터를 모두 제주데이터허브로 묶어 기재하지 않습니다. 원시 개인정보와 실제 키를 제출 파일에 넣지 않습니다.
