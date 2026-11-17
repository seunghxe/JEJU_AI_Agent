from pathlib import Path
from html.parser import HTMLParser
import pytest
import agent_service as mod

@pytest.fixture
def svc(monkeypatch):
    for key in ("KAKAO_REST_API_KEY","GEMINI_API_KEY","DATA_GO_KR_SERVICE_KEY","JEJU_DATAHUB_PROJECT_KEY"):
        monkeypatch.setenv(key,"")
    return mod.AgentService(Path(__file__).resolve().parents[1]/"data")

def test_wait_priority_reorders(svc,monkeypatch):
    first=svc.ask("성산일출봉")
    chosen=first["alternatives"][0]["id"]
    monkeypatch.setattr(svc.datahub,"station_context",lambda fid,*args: {"level":"low" if fid==chosen else "high","penalty":0})
    assert svc.ask("성산일출봉",preference="대기 위험 우선")["A"]["id"]==chosen

def test_travel_priority_checks_minutes(svc,monkeypatch):
    monkeypatch.setenv("KAKAO_REST_API_KEY","unit-test")
    monkeypatch.setattr(mod,"search_place",lambda *_:None)
    used={}
    def route(x,y,a,b):
        used.setdefault((a,b),len(used))
        return {"minutes":10-used[a,b],"distance_km":2}
    monkeypatch.setattr(mod,"driving_route",route)
    result=svc.ask("성산일출봉",preference="이동시간 우선")
    assert result["A"]["driving"]["minutes"]==6
    assert "확인된 차량시간" in result["basis"]

def test_backup_priority_and_no_route(svc):
    result=svc.ask("성산일출봉",preference="Plan B 우선")
    assert result["B"] and result["B"]["id"]!=result["A"]["id"]
    assert result["B"].get("reach") is None
    assert "직선거리 순" in svc.ask("성산일출봉",preference="이동시간 우선")["basis"]

def test_independent_controls_and_popup(svc):
    root=Path(__file__).resolve().parents[1]/"static"
    class Panels(HTMLParser):
        def __init__(self):
            super().__init__();self.stack=[];self.owners={}
        def handle_starttag(self,tag,attrs):
            i=dict(attrs).get("id")
            if tag=="details": self.stack.append(i)
            if i in ("vehicleSel","prefTiles"):self.owners[i]=self.stack.copy()
        def handle_endtag(self,tag):
            if tag=="details":self.stack.pop()
    panels=Panels();panels.feed((root/"index.html").read_text(encoding="utf8"))
    assert panels.owners=={"vehicleSel":["settingsBox"],"prefTiles":["criteriaBox"]}
    points=svc.station_points()
    assert len(points)==900 and all(p[4]["directions"] and p[4]["chargers"]>0 for p in points)
    assert ".bindPopup(infoPopup" in (root/"app.js").read_text(encoding="utf8")
