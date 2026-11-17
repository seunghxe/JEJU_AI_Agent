"""Generate reproducible local verification evidence, without live credentials."""
from pathlib import Path
import hashlib
import importlib.metadata as md
import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    if (ROOT / '.env').exists():
        raise SystemExit('Run verification in a clean copy without .env; never overwrite your settings.')
    for name in list(os.environ):
        if name.startswith(('GEMINI_', 'KAKAO_', 'DATA_GO_KR_', 'JEJU_DATAHUB_', 'LANGSMITH_', 'LANGCHAIN_')):
            os.environ.pop(name)
    commands = [[sys.executable, '-m', 'pytest', '-q', 'tests'],
                ['node', '--check', 'static/app.js'],
                ['node', 'tests/check_garage_ui.cjs'],
                ['node', 'tests/check_status_ui.cjs'],
                [sys.executable, '-m', 'pip', 'check']]
    checks = []
    for cmd in commands:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        output = (p.stdout + p.stderr).replace(str(ROOT.parent), '<workspace>')
        checks.append({'command': ['python' if x == sys.executable else x for x in cmd],
                       'exit_code': p.returncode, 'output': output})
    from fastapi.testclient import TestClient
    from server import app
    client = TestClient(app)
    hub_status = client.get('/api/status').json()['datahub']
    examples = []
    for query in ['성산일출봉 근처 충전소 찾아줘. 배터리는 30%야', 'Plan A는 빼고 다시 찾아줘', 'zzqqxx']:
        r = client.post('/api/ask', json={'query': query, 'thread_id': 'release-verification'})
        data = r.json()
        examples.append({'query': query, 'http_status': r.status_code,
                         **{k:data.get(k) for k in ('ok','battery','memory','clarify','summary')},
                         'A': (data.get('A') or {}).get('name'), 'B': (data.get('B') or {}).get('name')})
    hashes = {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
              for p in [*(ROOT/'data').glob('*.csv'), ROOT/'data/hub_snapshot.json', ROOT/'static/charge_history.json']}
    report = {'checked_at':datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),
              'python':platform.python_version(), 'os':platform.system(),
              'mode':'No real API credentials; portable real Hub aggregates, mocked API tests, local API examples',
              'hub_status':hub_status,
              'checks':checks, 'examples':examples, 'data_sha256':hashes,
              'not_verified':['Windows','mobile browser','live external APIs','deployed URL','Docker build','real charging outcomes']}
    (ROOT/'docs/validation_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    inventory=[]
    for d in sorted(md.distributions(), key=lambda d:d.metadata['Name'].lower()):
        m=d.metadata
        inventory.append({'name':m['Name'],'version':d.version,
                          'license_expression':m.get('License-Expression'),
                          'license':m.get('License'), 'project_urls':m.get_all('Project-URL',[])})
    (ROOT/'docs/dependency_inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'checks':[{k:c[k] for k in ('command','exit_code')} for c in checks], 'examples':examples},ensure_ascii=False,indent=2))
    return int(any(c['exit_code'] for c in checks))


if __name__ == '__main__':
    raise SystemExit(main())
