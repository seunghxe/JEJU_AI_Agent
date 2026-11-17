from fastapi.testclient import TestClient
import server
from merchant_places import resolve_shop

def test_change_meeting_cafe_remembers_battery(monkeypatch):
    for key in ("GEMINI_API_KEY", "DATA_GO_KR_SERVICE_KEY", "KAKAO_REST_API_KEY", "JEJU_DATAHUB_PROJECT_KEY"):
        monkeypatch.setenv(key, "")
    client = TestClient(server.app)
    def ask(q):
        return client.post("/api/ask",json={"thread_id":"cafe-switch","query":q}).json()
    a = ask("함덕 델문도에서 친구랑 커피 마시기로 했어. 배터리는 24%인데 친구가 아직 출발도 안 했대. 카페에서 제일 가까운 곳보다 충전 기다릴 위험이 낮은 곳으로 찾아줘.")
    b = ask("친구가 약속 장소를 애월 봄날 카페로 바꿨어. 배터리는 아까랑 같아. 새 카페 근처로 Plan A랑 Plan B 다시 잡아줘.")
    assert a["ok"] and a["dest"]["name"] == "델문도" and a["preference"] == "대기 위험 우선"
    assert b["ok"] and b["dest"]["name"] == "봄날 카페" and b["battery"] == 24
    c = ask("Plan A는 빼고 다시 찾아줘")
    assert c["dest"]["name"] == "봄날 카페" and c["A"]["id"] != b["A"]["id"]
    d = ask("함덕 없는이름카페에서 친구랑 만나기로 했어")
    assert not d["ok"] and d["place_retry"] and not d.get("A")
    assert ask("목적지: 오는정김밥")["dest"]["name"] == "오는정김밥"

def test_district_hit_cannot_stand_in_for_requested_shop():
    assert resolve_shop("함덕 유리파도카페", lambda _: {"name":"함덕해수욕장"}) is None
    assert resolve_shop("함덕 유리파도카페", lambda _: {"name":"유리파도"})["name"] == "유리파도"
