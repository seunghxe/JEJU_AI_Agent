# 실행 데이터

제출 ZIP에는 stations.csv, tourist_spots.csv, vehicles.csv가 포함됩니다. 공개 GitHub판에서는 이용조건·원출처 확인 전 공개를 피하기 위해 제외했습니다. GitHub판을 로컬 실행하려면 제출 ZIP의 세 파일을 이 디렉터리에, static/charge_history.json을 static 디렉터리에 복사하세요. .gitignore가 공개 커밋을 막습니다.

제출판에는 사용자 제공 JSON 4종을 묶은 hub_snapshot.json도 포함됩니다. 공개 GitHub판에는 이 파일도 제외하므로 키 없는 재현을 위해 제출판에서 이 디렉터리로 복사하세요. 기존 API 키가 있어도 저장 집계만 사용하려면 JEJU_DATAHUB_MODE=snapshot으로 설정합니다. 출처·기간·변환·이용조건 미확인 사항은 루트 DATA_USAGE.md에 정리했습니다.
