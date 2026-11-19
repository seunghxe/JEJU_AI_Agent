"""Build submission and public-source ZIPs; never package local secrets/caches."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / 'deliverables'
PRIVATE_DATA = {'data/stations.csv','data/tourist_spots.csv','data/vehicles.csv','static/charge_history.json','data/hub_snapshot.json'}
EXCLUDED = {'.git','.venv','__pycache__','.pytest_cache','.hub-cache'}


def selected():
    for p in sorted(ROOT.rglob('*')):
        if not p.is_file() or p.is_symlink():
            continue
        rel = p.relative_to(ROOT)
        if set(rel.parts) & EXCLUDED or p.suffix in {'.pyc','.log','.zip'} or p.name == 'MANIFEST.sha256':
            continue
        if p.name.startswith('.env') and p.name != '.env.example':
            continue
        if p.name.startswith('EVALUATION_KEY_PRIVATE'):
            continue
        yield p, rel.as_posix()


def main():
    files = list(selected())
    patterns = [rb'AIza[0-9A-Za-z_-]{30,}',rb'gh[pousr]_[0-9A-Za-z]{30,}',rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----']
    for path, rel in files:
        if any(re.search(pattern,path.read_bytes()) for pattern in patterns):
            raise SystemExit(f'Potential secret: {rel}; release stopped.')
    env=(ROOT/'.env.example').read_text(encoding='utf-8')
    for line in env.splitlines():
        if not line.startswith('#') and '=' in line:
            key,value=line.split('=',1)
            if ('KEY' in key or key.endswith('_CODE')) and value.strip():
                raise SystemExit('Nonempty secret/data-code example; release stopped.')
    OUT.mkdir(exist_ok=True)
    results=[]
    for filename,folder,public in [('Jeju_EV_PlanB_Submission.zip','Jeju_EV_PlanB',False),
                                   ('Jeju_EV_PlanB_GitHub.zip','Jeju_EV_PlanB',True)]:
        archive=OUT/filename
        manifest=[]
        with ZipFile(archive,'w',ZIP_DEFLATED) as z:
            for p,rel in files:
                if public and rel in PRIVATE_DATA:
                    continue
                z.write(p,folder+'/'+rel)
                manifest.append(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+rel)
            if not public and (ROOT / '.env').exists():
                p = ROOT / '.env'
                z.write(p, folder + '/.env')
                manifest.append(hashlib.sha256(p.read_bytes()).hexdigest() + '  .env')
            z.writestr(folder+'/MANIFEST.sha256','\n'.join(manifest)+'\n')
        with ZipFile(archive) as z:
            if z.testzip():
                raise SystemExit('ZIP integrity failure')
            names=z.namelist()
            if public:
                assert not any('/.env' in n and not n.endswith('/.env.example') for n in names)
            else:
                assert folder + '/.env' in names
            assert not any('/.hub-cache/' in n or '/.venv/' in n for n in names)
            if public:
                assert not any(n.removeprefix(folder+'/') in PRIVATE_DATA for n in names)
        results.append({'file':str(archive),'files':len(names),'bytes':archive.stat().st_size,
                        'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()})
    print(json.dumps(results,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
