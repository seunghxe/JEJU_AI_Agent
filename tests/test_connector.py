from fastapi.testclient import TestClient
import server
client = TestClient(server.app)

def test_other_requires_connector():
    r=client.post('/api/ask',json={'query':'성산일출봉','vehicle':'기타 전기차'}).json()
    assert not r['ok'] and '충전 규격' in r['summary']

def test_unsupported_not_recommended():
    for c in ['DC차데모','AC3상','AC완속','NACS','모름']:
        r=client.post('/api/ask',json={'query':'성산일출봉','vehicle':'기타 전기차','connector':c}).json()
        assert not r['ok'] and not r.get('A') and not r.get('B')

def test_combo_and_followup():
    p={'query':'성산일출봉','vehicle':'기타 전기차','connector':'DC콤보','thread_id':'connector-test'}
    r=client.post('/api/ask',json=p).json()
    assert r['ok'] and r['A'] and r['B'] and 'plan_b_search' in r
    assert not client.post('/api/ask',json={**p,'query':'다시 찾아줘','connector':'AC완속'}).json()['ok']

def test_visible_help_and_cache_version():
    r=client.get('/')
    assert r.headers['cache-control']=='no-store'
    for t in ['criteriaBox','이동시간 우선','대기 위험 우선','Plan B 우선','connectorSel','/static/app.js?v=','carArt','kakao-view.js']:
        assert t in r.text
