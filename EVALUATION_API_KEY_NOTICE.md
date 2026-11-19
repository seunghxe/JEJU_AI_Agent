# 평가용 API Key 안내

본 최종 제출 ZIP의 `.env`에는 심사 실행에 필요한 평가용 API Key가 포함되어 있습니다. 실제 키는 코드·보고서·공개 GitHub에는 작성하지 않았습니다.

## 적용된 변수

- `GEMINI_API_KEY`: 자연어 조건 구조화와 결과 설명
- `KAKAO_REST_API_KEY`: 장소 검색과 자동차 경로 조회
- `DATA_GO_KR_SERVICE_KEY`: 한국환경공단 충전기 현재 상태 조회
- `JEJU_DATAHUB_PROJECT_KEY`와 네 개의 데이터 코드: 원자료 갱신 경로 확인

제출판의 `JEJU_DATAHUB_MODE=snapshot` 설정은 동봉된 제주데이터허브 집계자료를 즉시 읽도록 합니다. 따라서 일반 추천 실행 시 데이터허브 전체 원자료를 다시 내려받지 않습니다. API 재수집을 확인할 때만 모드를 `auto` 또는 `api`로 변경합니다.

`KAKAO_MAP_JS_KEY`가 비어 있으면 Leaflet·OpenStreetMap 지도를 사용합니다. 장소 검색과 차량 경로는 REST 키로 별도 동작합니다.

## 실행

Python 3.12 가상환경에서 다음 명령을 실행합니다.

```bash
python -m pip install -r requirements.txt
python server.py
```

브라우저에서 `http://localhost:8501`에 접속합니다. 외부 API가 실패해도 규칙 기반 해석, 저장된 과거 집계, 직선거리 표시로 제한 실행됩니다.

평가용 키는 공개 저장소에 업로드하지 않으며, 호출량·비용 한도를 적용하고 평가 종료 후 폐기합니다.
