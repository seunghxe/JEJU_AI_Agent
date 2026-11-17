"""Package four validated cache aggregates without a project key.

Usage: python tools/package_hub_snapshot.py path/to/weekly.json path/to/daily.json path/to/wait.json path/to/floating.json
Each input kind is identified by its keys, not its opaque cache filename.
The generated file is for the authorized submission; publication rights are separate.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATTRS = {'weekly':('weekly',), 'daily':('daily_percentile',),
         'wait':('wait','wait_counts'), 'floating':('floating_percentile',)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs=4, type=Path)
    args = parser.parse_args()
    datasets = {}
    for path in args.inputs:
        raw = path.read_bytes()
        data = json.loads(raw)
        matches = [kind for kind, fields in ATTRS.items() if set(data) == {'details',*fields}]
        if len(matches) != 1 or matches[0] in datasets:
            raise SystemExit('Unrecognized or duplicate dataset')
        kind=matches[0]
        detail=data['details']
        allowed={'start','end','rows','matched','complete','row_checks','raw_unique'}
        if not isinstance(detail,dict) or not set(detail)<=allowed or detail.get('complete') is not True:
            raise SystemExit('Incomplete or unrecognized metadata')
        datasets[kind]={**data,'input_sha256':hashlib.sha256(raw).hexdigest()}
    catalogue=ROOT/'data/stations.csv'
    snapshot={'schema_version':1,'source':'사용자 제공 제주데이터허브 API 저장 집계',
              'packaged_date':'2026-11-18','collected_at':None,
              'catalogue_sha256':hashlib.sha256(catalogue.read_bytes()).hexdigest(),
              'datasets':datasets}
    out=ROOT/'data/hub_snapshot.json'
    out.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(out),'matched':{k:v['details']['matched'] for k,v in datasets.items()}},ensure_ascii=False))


if __name__=='__main__':
    main()
