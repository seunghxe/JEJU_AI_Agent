import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for key in ["GEMINI_API_KEY", "KAKAO_REST_API_KEY", "DATA_GO_KR_SERVICE_KEY"]:
    os.environ[key] = ""

from fastapi.testclient import TestClient  # noqa: E402
import server  # noqa: E402

client = TestClient(server.app)


def test_index_and_meta():
    assert client.get("/").status_code == 200
    meta = client.get("/api/meta").json()
    assert meta["stations"] == 900 and len(meta["vehicles"]) >= 1
    assert meta["status"]["live"]["state"] == "off"


def test_ask_returns_plan_a_and_b():
    res = client.post("/api/ask", json={"query": "내일 어리목에서 한라산 탐방해. 배터리 30%야"}).json()
    assert res["ok"] and res["A"]["name"] == "어리목 공영주차장"
    assert res["B"] and res["battery"] == 30
    assert any("대체시설" in n["text"] for n in res["notes"])
    assert [t["step"] for t in res["trace"]][0] == "질문 이해"


def test_ask_with_origin_checks_battery():
    res = client.post("/api/ask", json={"query": "성산일출봉 근처 충전소", "origin": "애월읍", "battery": 10}).json()
    assert res["origin"] and any(n["tone"] == "warn" for n in res["notes"])


def test_unknown_place_is_handled():
    res = client.post("/api/ask", json={"query": "zzqqxx"}).json()
    assert res["ok"] is False and res["clarify"] and "어느 동네" in res["summary"]


def test_station_points():
    pts = client.get("/api/stations").json()
    assert len(pts) == 900 and len(pts[0]) == 5 and pts[0][4]["directions"]


def test_station_live_endpoint_without_api_key():
    facility_id = "test-facility"
    res = client.get(f"/api/live/station/{facility_id}")
    assert res.status_code == 200
    assert res.json()["ok"] is False


def test_ask_includes_kakao_driving_time_when_connected(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY", "test-key")
    monkeypatch.setattr("agent_service.driving_route", lambda *args: {
        "minutes": 12, "distance_km": 7.8, "source": "Kakao Mobility"
    })
    res = client.post("/api/ask", json={"query": "성판악 근처 충전소"}).json()
    assert res["A"]["driving"]["minutes"] == 12
    assert res["B"]["driving"]["distance_km"] == 7.8


def test_multiturn_remembers_context_and_excludes_plan_a():
    thread_id = "test-multiturn-context"
    first = client.post("/api/ask", json={
        "query": "우도 쪽 충전소 찾아줘. 배터리는 22%야", "thread_id": thread_id
    }).json()
    second = client.post("/api/ask", json={
        "query": "Plan A는 빼고 대기 위험이 낮은 곳으로 다시 찾아줘", "thread_id": thread_id
    }).json()
    assert first["ok"] and second["ok"]
    assert second["dest"]["name"] == first["dest"]["name"]
    assert second["A"]["id"] != first["A"]["id"]
    assert second["battery"] == 22
    assert second["memory"]["excluded_count"] == 1
    assert second["memory"]["excluded_count"] >= 1
    assert second["memory"]["turn_count"] == 2


def test_new_conversation_can_be_cleared():
    thread_id = "test-clear-context"
    client.post("/api/ask", json={"query": "성산일출봉 충전소", "thread_id": thread_id})
    res = client.delete(f"/api/conversation/{thread_id}")
    assert res.status_code == 200 and res.json()["ok"] is True
