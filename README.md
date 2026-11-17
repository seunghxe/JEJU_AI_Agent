# 제주 EV Plan B AI Agent

목적지와 차량·배터리 조건을 바탕으로 충전소 Plan A와 대안 Plan B를 함께 비교하는 웹 에이전트입니다. 과거 운영·이용 자료를 참고하고, API 설정 시 현재 상태와 차량 경로를 확인합니다. 목적지·배터리·제외 조건을 기억해 후속 추천을 수행합니다.

팀: 작전명청춘 / 패키지 작성: 2026-11-18

## 먼저 확인

- Python 3.12 권장. 이번 검증은 Linux Python 3.12.14에서 수행했습니다. Windows 최종 확인은 필요합니다. Python 3.14 가상환경은 재사용하지 마세요.
- 제출 ZIP은 900곳 분석 자료와 281곳 과거 이력을 포함합니다. 공개 GitHub ZIP에서는 데이터 CSV 3개와 과거 이력 JSON을 제외했습니다. GitHub판 실행 전 제출판의 해당 파일을 로컬로 복사해야 합니다.
- 제출판에는 사용자 제공 JSON 4종을 검증한 `data/hub_snapshot.json`을 포함합니다. **키가 없어도 허브 과거 집계 4종을 즉시 읽습니다.** 공개 GitHub판에서는 이 파일도 제외하므로 실행 전 제출판에서 복사해야 합니다.
- `JEJU_DATAHUB_MODE=auto`는 키·코드가 있으면 API, 없으면 동봉 집계를 사용합니다. `snapshot`은 키가 있어도 저장 집계만 사용하며, `api`는 API만 사용합니다. 기존 키가 든 `.env`에서 다운로드를 피하려면 `snapshot`으로 설정하세요.
- 키가 없어도 허브 과거 집계와 규칙 추천은 동작하지만, 실시간 상태·Gemini·카카오 차량시간은 제공되지 않습니다. 화면에 ‘저장 자료 사용 · 데이터 4종’으로 구분합니다.
- 제출 전 [확인사항](docs/00_RELEASE_CHECKLIST.md)을 확인하세요. 15페이지 이내 기획서는 별도 제출입니다.

## Windows / VS Code

새 폴더에 압축을 풀고 server.py가 있는 폴더를 VS Code로 엽니다. 터미널에서 한 줄씩 실행합니다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe server.py
```

이미 `.env`가 있으면 복사 명령은 생략하세요. 키는 로컬 `.env`에만 입력합니다. 접속: http://localhost:8501 / 종료: Ctrl+C. `run_windows.bat`도 사용할 수 있습니다. `py -3.12`가 없으면 Python 3.12와 Windows Python Launcher 설치 후 VS Code를 다시 엽니다.

## macOS / Linux

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
.venv/bin/python server.py
```

기존 설정이 있으면 복사 명령을 생략하세요. 전체 설치 버전은 `requirements-tested.txt`에 기록했습니다. 다른 운영체제에서의 설치 가능성은 확인이 필요합니다.

## 사용 예

1. **내 차**: 차량·규격·배터리·선택적 출발지 입력.
2. **충전소 추천 기준**: 균형 / 이동시간 / 대기 위험 / Plan B 우선 선택.
3. `성산일출봉 근처 충전소 찾아줘. 배터리는 30%야` 입력.
4. Plan A/B의 현재 상태·이동 기준·근거 출처 비교.
5. `Plan A는 빼고 다시 찾아줘`로 후속 추천.
6. 카카오맵 길찾기로 이동. 예약·결제·자동 차량 제어는 수행하지 않습니다.

## 실행 모드

| 설정 | 활성 기능 | 미설정·실패 시 |
|---|---|---|
| GEMINI_API_KEY | 질문 구조화·답변 요약 | 규칙 해석·정해진 문장 |
| KAKAO_REST_API_KEY | 장소 검색·자동차 경로 | 내장 장소·직선거리/경로 미확인 |
| KAKAO_MAP_JS_KEY | 카카오 배경지도 | Leaflet + OpenStreetMap |
| DATA_GO_KR_SERVICE_KEY | 현재 충전기 상태 | 과거 기록·현재 상태 미확인 |
| JEJU_DATAHUB_PROJECT_KEY와 *_CODE | 허브 API 이력·방문수요 | auto/snapshot에서는 동봉 허브 집계 사용 |

API·지도·사진에는 인터넷이 필요합니다. 무료 쿼터·모델 접근은 계정과 제공처 정책에 따릅니다. 실제 키를 공개하지 마세요.

## 문서

- [설치·키 설정·사용자 매뉴얼](docs/01_MANUAL.md)
- [데이터 활용 명세](DATA_USAGE.md)
- [결과 설명자료](docs/02_RESULT_REPORT.md)
- [검증 방법·결과](docs/03_VALIDATION.md)
- [AI·모델·외부 자료 내역](docs/04_ATTRIBUTION.md)
- [GitHub·데모 배포](docs/05_GITHUB_DEPLOY.md)
- [프롬프트·API 명세](docs/06_PROMPTS_TOOLS.md)

## 검증

```bash
python -m pytest -q tests
node tests/check_garage_ui.cjs
node tests/check_status_ui.cjs
```

Node.js는 UI 로직 테스트에만 필요합니다. 테스트에는 더미 API 응답이 포함됩니다. 통과가 실서비스 API나 대기시간 개선을 입증하지 않습니다.

## 배포와 한계

`render.yaml`, `Dockerfile`을 제공합니다. 공개 데모 URL은 아직 발급·검증하지 않았습니다. GitHub Pages만으로 Python 서버를 실행할 수 없습니다. 서버 권한·데이터 배치·환경변수 설정이 필요합니다.

과거 자료는 도착 시 가용성을 보장하지 않습니다. 배터리 도달 판단은 대표 전비·직선거리 기반 참고값입니다. 대화 기억은 서버 재시작 시 초기화됩니다. 브라우저가 열린 동안 상태를 점검하며 백그라운드 내비게이션을 대체하지 않습니다.
