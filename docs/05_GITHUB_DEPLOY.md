# GitHub 업로드·실행 데모 배포

## 1. 두 ZIP의 차이

제출 ZIP은 실행 코드·분석 데이터·허브 휴대형 집계·문서·검증 결과와 심사용 `.env`를 담습니다. GitHub 공개본에서는 `.env`, 원본 키 의존 캐시, 가상환경과 비공개 평가용 키를 제외합니다. 공개 저장소에서 전체 데이터를 제외한 경우 제출 ZIP의 데이터 파일을 동일 위치에 배치해야 로컬 실행할 수 있습니다.

## 2. GitHub 공개 소스 저장소

최종 공개 저장소: https://github.com/seunghxe/JEJU_AI_Agent

저장소를 다시 올리거나 수정할 경우 다음 절차를 사용합니다.

1. 사용자 지정 계정 **seunghxe**로 GitHub에 로그인하고 위 저장소를 엽니다.
2. GitHub ZIP을 풀고 server.py와 README.md가 있는 폴더를 VS Code로 열기.
3. 원격 저장소 주소는 `https://github.com/seunghxe/JEJU_AI_Agent.git`을 사용합니다.
4. 명령 실행 전 `git status`에 `.env`·허브 캐시·개인 로그가 없는지 확인.

```powershell
git init
git add .
git status
git commit -m "Prepare Jeju EV Plan B submission"
git branch -M main
git remote add origin https://github.com/seunghxe/JEJU_AI_Agent.git
git push -u origin main
```

이미 Git 저장소인 폴더라면 init/remote 추가를 반복하지 말고 기존 원격을 확인하세요. 저장소 주소를 대회 GitHub란에 넣습니다. 비공개라면 심사위원 접근 방법을 운영진에 확인해야 합니다.

GitHub판 로컬 실행은 제출 ZIP에서 data/stations.csv, data/tourist_spots.csv, data/vehicles.csv, static/charge_history.json, data/hub_snapshot.json 다섯 파일을 동일 위치에 복사한 뒤 README 절차를 따릅니다. .gitignore로 공개 커밋을 막았습니다.

## 3. 실제 Python 데모 배포

최종 공개 데모: https://jeju-ev-planb-ai-agent.onrender.com

데모는 Render의 Python/FastAPI 웹 서비스로 배포했습니다. 무료 인스턴스는 유휴 상태 후 첫 접속 시 시작 시간이 걸릴 수 있습니다. GitHub Pages만으로는 이 서버를 실행할 수 없습니다.

Render는 공식적으로 FastAPI 웹 서비스를 지원합니다. 참조: https://render.com/docs/deploy-fastapi , https://render.com/docs/free . 무료 인스턴스는 15분 유휴 후 정지할 수 있고 재시작에는 시간이 걸리며 로컬 파일 변경이 사라질 수 있습니다. 세션 기억과 캐시도 지속된다고 가정하지 마세요.

### 배포 순서

1. 실제 자료의 배포 이용조건을 확인한 뒤, 별도 **비공개 배포 저장소**에 제출용 코드를 준비합니다. 비공개여도 이용허락을 대신하지 않습니다.
2. 데이터 다섯 파일을 서버에서 읽을 수 있어야 합니다. 사용 권한을 확인했다면 `.gitignore`의 해당 다섯 제외 항목을 배포용 저장소에서만 제거해 추가합니다. `.env`·원 캐시·평가용 키 제외 규칙은 유지합니다.
3. Render에서 New → Web Service → 해당 저장소 연결. 루트는 server.py가 있는 폴더.
4. Runtime Python, Python 3.12, Build Command `pip install -r requirements.txt`.
5. Start Command `uvicorn server:app --host 0.0.0.0 --port $PORT --workers 1`.
6. Free 요금제와 계정 사용량 조건을 확인. render.yaml은 같은 설정의 Blueprint용 파일입니다.
7. 환경변수 JEJU_DATAHUB_MODE=snapshot이면 동봉 허브 자료를 바로 사용합니다. 실시간·Gemini·카카오 경로가 필요하면 서버 환경변수에 해당 키 입력. `.env` 파일은 업로드하지 않습니다. API 재수집이 필요할 때만 허브 모드와 키·코드를 변경합니다.
8. Deploy 완료 후 서비스가 반환하는 실제 HTTPS URL 확인. 카카오 지도 사용 시 허용 도메인 추가.
9. 로그아웃 브라우저에서 메인 화면·추천·후속 요청·지도·API 상태를 확인하고 위 데모 URL을 제출.

개발 API는 인증·사용자별 속도 제한이 없습니다. 공개 데모에 유료 키를 연결하기 전에 제공처 쿼터·비용 제한과 호스팅 접근 제어를 설정해야 합니다. 테스트/심사용 소규모 데모를 상시 공개 운영 서비스로 간주하지 마세요. 평가 종료 후 평가용 키를 폐기합니다.

### Docker 대안

Docker를 사용할 수 있는 환경에서, 네 데이터 파일이 있는 제출판 루트에서 실행합니다.

```bash
docker build -t jeju-ev-planb .
docker run --rm --env-file .env -p 8501:8501 jeju-ev-planb
```

Docker 자체 빌드·실배포는 이번 검증에서 실행하지 않았습니다. 포트·컨테이너 메모리·외부 통신을 확인하세요.

## 4. 영상

2~3분: 차량/배터리 → 목적지 → A/B → 허브 추천 근거 → A 제외 후속 요청 → 길찾기. 실제 키·계정 개인정보가 화면에 보이지 않게 촬영하세요. 영상 URL과 데모 URL은 서로 대체하지 않습니다. 배포가 준비되지 않으면 데모란에 localhost를 넣지 않습니다.
