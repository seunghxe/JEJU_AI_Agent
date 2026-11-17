from pathlib import Path
import pandas as pd
from agent_service import AgentService


def make_service(monkeypatch):
    service=AgentService(Path(__file__).resolve().parents[1]/'data')
    base=service.stations.iloc[0].copy()
    rows=[]
    for id,name,lat,region in [('a','A',33.40,'제주본섬'),('b','B',33.41,'제주본섬'),('c','C',33.42,'제주본섬'),('d','섬시설',33.415,'우도'),('e','동일지점',33.40001,'제주본섬')]:
        row=base.copy();row['시설 ID']=id;row['대표충전소 ID']=id;row['충전소명']=name
        row['위도']=lat;row['경도']=126.5;row['도로권역']=region
        rows.append(row)
    service.stations=pd.DataFrame(rows)
    service.by_id=service.stations.set_index('시설 ID')
    a=service.stations.iloc[0].copy()
    a['PlanB시설그룹아이디']='b';a['PlanB대표충전소명']='B';a['PlanB_위도']=33.41;a['PlanB_경도']=126.5
    service._live={id:{'available':1 if id in ('c','d','e') else 0,'charging':0,'total':1} for id in ('a','b','c','d','e')}
    monkeypatch.setenv('KAKAO_REST_API_KEY','')
    monkeypatch.setenv('DATA_GO_KR_SERVICE_KEY','test')
    return service,a


def test_research_skips_blocked_island_and_same_point(monkeypatch):
    s,a=make_service(monkeypatch)
    b,info=s._select_plan_b(a)
    assert b['id']=='c' and info['changed'] and b['live']['tone']=='good'


def test_keeps_available_original(monkeypatch):
    s,a=make_service(monkeypatch);s._live['b']['available']=1
    b,info=s._select_plan_b(a)
    assert b['id']=='b' and not info['changed']


def test_no_confirmed_backup_and_exclusions(monkeypatch):
    s,a=make_service(monkeypatch)
    b,info=s._select_plan_b(a,['c'])
    assert b is None and info['state']=='none'
    s._live.pop('c')
    assert s._select_plan_b(a)[0] is None


def test_offline_keeps_historical_as_unverified(monkeypatch):
    s,a=make_service(monkeypatch);monkeypatch.setenv('DATA_GO_KR_SERVICE_KEY','')
    b,info=s._select_plan_b(a)
    assert b['id']=='b' and info['state']=='unverified'


def test_recheck_unknown_facility(monkeypatch):
    s,a=make_service(monkeypatch)
    assert s.recheck_plan_b('missing')['ok'] is False
