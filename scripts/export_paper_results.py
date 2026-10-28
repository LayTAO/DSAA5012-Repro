#!/usr/bin/env python3
"""Export bounded paper-comparison records, excluding every large data/core file."""
import argparse
import hashlib
import json
from pathlib import Path
from benchmark import ROOT


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',default='001')
    args=parser.parse_args()
    if not args.run_id.isalnum():
        parser.error('Run ID must be alphanumeric')
    package={}
    def add(name,path):
        if path.stat().st_size>131072:
            raise RuntimeError('Refusing export larger than 128 KiB: '+str(path))
        package[name]=path.read_text().replace(str(ROOT),'${PROJECT_ROOT}')
    registry=json.loads((ROOT/'configs/paper-batch.json').read_text())
    for dataset,spec in registry.items():
        output=ROOT/'results'/('paper-'+dataset+'-'+args.run_id)
        for name in ['summary.json','metadata.json','runs.jsonl','validation.json']:
            add(dataset+'/'+name,output/name)
        add(dataset+'/data-manifest.json',ROOT/'data/processed'/spec['directory']/'manifest.json')
        metadata=json.loads((output/'metadata.json').read_text())
        manifest=json.loads((ROOT/'data/processed'/spec['directory']/'manifest.json').read_text())
        if metadata['data']['sha256']!=manifest['processed']['sha256']:
            raise RuntimeError(dataset+': timed input differs from audited input')
        summary=json.loads((output/'summary.json').read_text())
        expected={'vldb_OPTIV',*(f'sigmod_{i}' for i in range(6))}
        rows=[json.loads(line) for line in (output/'runs.jsonl').read_text().splitlines()]
        validation=json.loads((output/'validation.json').read_text())
        if (len(summary['methods'])!=7 or {m['method'] for m in summary['methods']}!=expected
                or any(m['successful_runs']!=3 for m in summary['methods'])
                or len(rows)!=21 or any(r['status']!='ok' or r['exported_cores'] for r in rows)
                or {(r['method'],r['repeat']) for r in rows}!={(m,i) for m in expected for i in (1,2,3)}):
            raise RuntimeError(dataset+': not all runs completed')
        if (len(validation)!=7 or {r['method'] for r in validation}!=expected
                or any(r['status']!='ok' or r['vertices']!=metadata['data']['vertices'] for r in validation)
                or len({r['core_sha256'] for r in validation})!=1
                or summary['core_sha256']!=validation[0]['core_sha256']):
            raise RuntimeError(dataset+': full-output validation failed')
    for dataset in ['CO','GE','DF']:
        add('excluded-cornell-'+dataset+'.json',ROOT/'data/processed'/('cornell-'+dataset+'-ordered')/'manifest.json')
    add('correctness.json',ROOT/'results/correctness-002/summary.json')
    add('environment.json',ROOT/'results/setup/environment.json')
    add('environment-final.json',ROOT/'results/setup/environment-final.json')
    for name in ['paper-profile.json','paper-batch.json','paper-digitized.json','upstream.lock.json','data.lock.json']:
        add(name,ROOT/'configs'/name)
    sources=[ROOT/'scripts'/name for name in ['benchmark.py','prepare_cornell.py','prepare_author_data.py','run_paper_batch.py','fetch_data.py','build_drivers.sh','build_native.sh','digitize_paper.py','report_paper_results.py']]+list((ROOT/'src/drivers').glob('*'))
    package['source-checksums.json']=json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources if p.is_file() and not p.name.startswith('._')},indent=2)+'\n'
    payload=json.dumps(package)
    if len(payload.encode())>768*1024:
        raise RuntimeError('Summary package exceeds 768 KiB')
    print(payload)


if __name__=='__main__':
    main()
