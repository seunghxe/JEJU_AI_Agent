import uuid
from fastapi.testclient import TestClient
import server
import agent_service

client = TestClient(server.app)

def test_progress_and_clarification():
    token=str(uuid.uuid4())
    thread=str(uuid.uuid4())
    def ask(q):
        return client.post("/api/ask",json={"query":q,"thread_id":thread,"progress_id":token}).json()
    r=ask("함덕 없는이름카페에서 만나. 배터리는 24%야. 대기 위험 낮게")
    assert r["clarify"] and "어느 동네" in r["summary"]
    assert client.get("/api/progress/"+token).json()["step"] == 2
    found=ask("협재해수욕장 근처")
    assert found["ok"] and found["battery"]==24 and "협재" in found["dest"]["name"]
    assert client.get("/api/progress/"+token).json()["step"] == 6

def test_disambiguate_an_existing_shop_with_district(monkeypatch):
    thread=str(uuid.uuid4())
    def ask(q):return client.post("/api/ask",json={"query":q,"thread_id":thread}).json()
    assert ask("무지개별카페 근처 충전소. 배터리 32%")["clarify"]
    calls=[]
    def lookup(s):
        calls.append(s)
        return {"name":"무지개별카페","lat":33.46,"lon":126.32,"source":"테스트"}
    monkeypatch.setenv("KAKAO_REST_API_KEY","test")
    monkeypatch.setattr(agent_service,"search_place",lookup)
    monkeypatch.setattr(agent_service,"driving_route",lambda *args:None)
    r=ask("애월읍이야")
    assert calls==["애월읍 무지개별카페"] and r["ok"] and r["battery"]==32

def test_map_key_is_separate(monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY","only-server")
    monkeypatch.setenv("KAKAO_MAP_JS_KEY","only-server")
    assert client.get("/api/meta").json()["map_js_key"] == ""
    monkeypatch.setenv("KAKAO_MAP_JS_KEY","public-map")
    assert client.get("/api/meta").json()["map_js_key"] == "public-map"
