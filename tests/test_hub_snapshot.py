import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from jejudatahub_client import JejuDataHubClient

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def portable(tmp_path, monkeypatch):
    for key in list(__import__('os').environ):
        if key.startswith('JEJU_DATAHUB_'):
            monkeypatch.delenv(key)
    (tmp_path/'data').mkdir()
    (tmp_path/'static').mkdir()
    for name in ['stations.csv','hub_snapshot.json']:
        shutil.copy2(ROOT/'data'/name,tmp_path/'data'/name)
    shutil.copy2(ROOT/'static/charge_history.json',tmp_path/'static/charge_history.json')
    return tmp_path


def test_real_snapshot_loads_without_key_or_requests(portable):
    with patch('jejudatahub_client.requests.get', side_effect=AssertionError('network forbidden')):
        hub=JejuDataHubClient(portable/'static/charge_history.json')
        status=hub.refresh()
    assert status['mode']=='snapshot' and not hub.configured
    assert status['loaded']=={'weekly':346,'daily':340,'wait':16,'floating':43}
    assert status['errors']=={}
    assert len(hub.wait)==11 and sum(n==0 for n in hub.wait_counts.values())==5
    assert all(d['bundled'] and d['complete'] for d in status['details'].values())


def test_actual_aggregate_changes_recommendation_evidence(portable):
    hub=JejuDataHubClient(portable/'static/charge_history.json')
    ctx=hub.station_context('F0749',dong='애월읍',weekday='화')
    assert ctx['source']=='제주데이터허브'
    assert ctx['penalty']>0
    assert any('화요일' in s for s in ctx['evidence'])
    hub.weekly={};hub.wait={};hub.wait_counts={};hub.daily_percentile={};hub.floating_percentile={}
    assert (hub.station_context('F0749',dong='애월읍',weekday='화') or {}).get('source')!='제주데이터허브'


def test_explicit_snapshot_ignores_present_keys(portable,monkeypatch):
    monkeypatch.setenv('JEJU_DATAHUB_MODE','snapshot')
    monkeypatch.setenv('JEJU_DATAHUB_PROJECT_KEY','unit-not-real')
    monkeypatch.setenv('JEJU_DATAHUB_WEEKLY_CHARGE_CODE','unit')
    with patch('jejudatahub_client.requests.get',side_effect=AssertionError('network forbidden')):
        hub=JejuDataHubClient(portable/'static/charge_history.json')
        assert hub.refresh(force=True)['mode']=='snapshot'


def test_api_mode_does_not_pretend_snapshot_is_api(portable,monkeypatch):
    monkeypatch.setenv('JEJU_DATAHUB_MODE','api')
    hub=JejuDataHubClient(portable/'static/charge_history.json')
    assert hub.refresh()['loaded']=={}
    assert not hub.snapshot_loaded


@pytest.mark.parametrize('damage',['catalogue','number','matched','unknown_id','missing_kind','incomplete'])
def test_corrupt_snapshot_rejected_atomically(portable,damage):
    path=portable/'data/hub_snapshot.json'
    data=json.loads(path.read_text(encoding='utf-8'))
    if damage=='catalogue': data['catalogue_sha256']='wrong'
    if damage=='number': data['datasets']['floating']['floating_percentile']['애월읍']=1.5
    if damage=='matched': data['datasets']['weekly']['details']['matched']=1
    if damage=='unknown_id': data['datasets']['daily']['daily_percentile']['unknown']=0.4
    if damage=='missing_kind': del data['datasets']['wait']
    if damage=='incomplete': data['datasets']['daily']['details']['complete']=False
    path.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    hub=JejuDataHubClient(portable/'static/charge_history.json')
    assert not hub.loaded and not hub.weekly and not hub.floating_percentile
    assert 'snapshot' in hub.errors


def test_snapshot_reload_and_api_failure_clear_previous_state(portable,monkeypatch):
    hub=JejuDataHubClient(portable/'static/charge_history.json')
    assert hub.snapshot_loaded
    hub.mode='api';hub.project_key='unit';hub.codes={'weekly':'unit'}
    from unittest.mock import Mock
    with patch('jejudatahub_client.requests.get',return_value=Mock(status_code=403)):
        assert not hub.refresh(force=True)['loaded']
    assert not hub.snapshot_loaded and not hub.weekly


def test_missing_snapshot_keeps_legacy_fallback(portable):
    (portable/'data/hub_snapshot.json').unlink()
    hub=JejuDataHubClient(portable/'static/charge_history.json')
    assert not hub.loaded and len(hub.history)==281
