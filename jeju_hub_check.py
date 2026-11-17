"""Read-only status check. Share counts, never credentials or request URLs."""
from pathlib import Path
from dotenv import load_dotenv
from jejudatahub_client import BASE_URL, JejuDataHubClient


def main():
    root = Path(__file__).resolve().parent
    load_dotenv(root / ".env")
    c = JejuDataHubClient(root / "static/charge_history.json")
    if c.base_url != BASE_URL or not c.stations or (not c.configured and not c.snapshot_loaded):
        print("공식 API 설정과 시설 목록을 먼저 확인하세요.")
        return
    status = c.refresh()
    print("자료 모드:", status["mode"])
    for kind in dict.fromkeys([*status["configured_datasets"], *status["loaded"]]):
        d = status["details"].get(kind, {})
        print(kind, d.get("start", "-"), "~", d.get("end", "-"), "수신", d.get("rows", 0),
              "연결 시설/지역", d.get("matched", 0))
        if d.get("row_checks"):
            print("행 기준:", " / ".join(f"{k} {v}" for k, v in d["row_checks"].items()))
        if status["errors"].get(kind):
            print(status["errors"][kind])


if __name__ == "__main__":
    main()
