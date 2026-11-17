"""한국환경공단 충전기 정보 API로 제주 충전기 현재 상태를 조회한다."""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import requests

CHARGER_INFO_URL = "https://apis.data.go.kr/B552584/EvCharger/getChargerInfo"
STATUS_LABELS = {"1": "통신 이상", "2": "충전 가능", "3": "충전 중", "4": "운영 중지", "5": "점검 중", "9": "상태 미확인"}
# DC콤보를 지원하는 충전기 타입 (04 DC콤보, 05 DC차데모+DC콤보, 06 DC차데모+AC3상+DC콤보, 10 DC콤보+NACS)
DC_COMBO_TYPES = {"04", "05", "06", "10"}
KST = timezone(timedelta(hours=9))


def _is_fast_combo(item: ET.Element) -> bool:
    ctype = (item.findtext("chgerType") or "").strip()
    output = (item.findtext("output") or "").strip()
    if ctype and ctype not in DC_COMBO_TYPES:
        return False
    try:
        return not output or float(output) >= 50
    except ValueError:
        return True


def fetch_jeju_status() -> tuple[dict[str, dict], str | None]:
    """{충전소ID: {available, charging, total, chargers}}와 오류 메시지를 반환한다."""
    service_key = os.getenv("DATA_GO_KR_SERVICE_KEY", "").strip()
    if not service_key:
        return {}, "공공데이터포털 인증키가 설정되지 않았습니다."
    try:
        response = requests.get(
            CHARGER_INFO_URL,
            params={"serviceKey": service_key, "pageNo": 1, "numOfRows": 9999, "zcode": 50},
            timeout=25,
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
        result_code = root.findtext(".//resultCode")
        if result_code not in (None, "00"):
            return {}, root.findtext(".//resultMsg") or f"API 오류 {result_code}"

        summary: dict[str, dict] = {}
        for item in root.findall(".//item"):
            station_id = item.findtext("statId")
            if not station_id or not _is_fast_combo(item):
                continue
            code = item.findtext("stat") or "9"
            s = summary.setdefault(station_id, {"available": 0, "charging": 0, "total": 0, "chargers": []})
            s["total"] += 1
            s["available"] += code == "2"
            s["charging"] += code == "3"
            s["chargers"].append({"charger_id": item.findtext("chgerId"), "status": STATUS_LABELS.get(code, "알 수 없음")})
        return summary, None
    except (requests.RequestException, ET.ParseError, ValueError) as exc:
        return {}, f"실시간 상태를 불러오지 못했습니다 ({type(exc).__name__})"


def now_kst_text() -> str:
    return datetime.now(KST).strftime("%H:%M")
