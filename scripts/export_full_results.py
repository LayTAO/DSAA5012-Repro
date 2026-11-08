#!/usr/bin/env python3
"""Export only bounded metadata; never transfer graphs, binaries or core CSV files."""
import json
from pathlib import Path
from benchmark import ROOT,digest


def main():
    package={}
    def add(path):
        if not path.is_file():return
        if path.stat().st_size>2*1024**2:raise RuntimeError('Metadata exceeds 2 MiB: '+str(path))
        name=str(path.relative_to(ROOT))
        package[name]=path.read_text().replace(str(ROOT),'${PROJECT_ROOT}').replace('/home/taolei/DSAA5012-Repro','${ORIGINAL_PROJECT_ROOT}')
    for name in ['full-datasets.json','synthetic-profile.json','paper-profile.json','paper-digitized.json','paper-extended-reference.json','upstream.lock.json','methods.json']:
        add(ROOT/'configs'/name)
    registry=json.loads((ROOT/'configs/full-datasets.json').read_text())
    for key,spec in registry.items():
        add(ROOT/'data/processed'/spec['directory']/'manifest.json')
        if spec.get('existing_result'):
            for name in ['metadata.json','summary.json','validation.json','runs.jsonl']:
                add(ROOT/'results'/spec['existing_result']/name)
    for key in ['AMZ','TAS','SOA','AM']:add(ROOT/'data/processed'/('scales-'+key)/'manifest.json')
    for key in ['POW-S-approx','POW-L-approx']:add(ROOT/'data/processed'/('synthetic-'+key)/'manifest.json')
    failures=[]
    for name in ['full-real-001','full-synthetic-small001','full-synthetic-large001','full-workflow-001']:
        for path in (ROOT/'results'/name).glob('*.json'):
            add(path)
            row=json.loads(path.read_text())
            if row.get('repeat',0)>0 and row.get('status')!='ok':
                evidence={k:row.get(k) for k in ['label','dataset','argument','status','exit_code','repeat','process_wall_s','peak_rss_kib','memory_limit_bytes','timeout_s','reused_attempt','binary_sha256','input_sha256']}
                evidence['record']=str(path.relative_to(ROOT));evidence['record_sha256']=digest(path)
                stem=row.get('reused_attempt',row['label'])
                for suffix in ['.log','.time.txt']:
                    log=path.parent/(stem+suffix)
                    if log.exists():
                        with log.open('rb') as stream:
                            stream.seek(max(0,log.stat().st_size-4096));tail=stream.read().decode(errors='replace')
                        evidence['log_tail' if suffix=='.log' else 'gnu_time_tail']=tail.replace(str(ROOT),'${PROJECT_ROOT}')
                failures.append(evidence)
    package['results/failure-evidence.json']=json.dumps({'records':failures,'interpretation':'Exit 139 / signal 11 is SIGSEGV, not proof of OOM. Preserve the recorded status until root cause is independently established.'},indent=2)+'\n'
    for name in ['correctness-002','extended-correctness-002','data-tools-check-001']:
        add(ROOT/'results'/name/'summary.json')
    for name in ['extended-adaptations.json','sampling-adaptations.json','environment.json','environment-final.json']:
        add(ROOT/'results/setup'/name)
    sources=[p for folder in ['scripts','src/drivers','tests'] for p in (ROOT/folder).glob('*') if p.is_file() and p.suffix in ['.py','.sh','.cpp','.h'] and not p.name.startswith('._')]
    package['source-checksums.json']=json.dumps({str(p.relative_to(ROOT)):digest(p) for p in sources},indent=2)+'\n'
    payload=json.dumps(package)
    if len(payload.encode())>32*1024**2:raise RuntimeError('Metadata package exceeds 32 MiB')
    print(payload)

if __name__=='__main__':main()
