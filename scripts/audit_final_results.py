#!/usr/bin/env python3
"""Final server-side integrity audit. Rehash inputs/binaries; retain all failures."""
import collections
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITES = ['full-real-001', 'full-synthetic-small001', 'full-synthetic-large001']


def read(p):
    return json.loads(p.read_text())


def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(8 * 1024**2), b''):
            h.update(b)
    return h.hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def main():
    if str(ROOT) != '/data/taolei/DSAA5012-Repro-full':
        raise RuntimeError('Run through run_on_server.sh in the approved server project')
    if ROOT.stat().st_dev == Path('/').stat().st_dev:
        raise RuntimeError('Project must not be on the root filesystem')
    out = ROOT / 'results/final-audit-001'
    out.mkdir(exist_ok=True)
    locks = []
    for p in [ROOT/'results/full-workflow-001/workflow.lock'] + [ROOT/'results'/s/'runner.lock' for s in SUITES]:
        f = p.open('r'); fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB); locks.append(f)
    f = (out/'audit.lock').open('a'); fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB); locks.append(f)
    (out/'audit.pid').write_text(str(os.getpid())+'\n')
    final = out/'audit.json'
    if final.exists():
        print('Existing audit retained:', final, flush=True)
        return
    report = {'started_at_utc':now(), 'status':'running', 'root_device':Path('/').stat().st_dev,
              'project_device':ROOT.stat().st_dev, 'issues':[], 'inputs':[], 'binaries':[],
              'runner_sources':[], 'full_core_records':[], 'failure_records':[]}
    def check(condition, message):
        if not condition: report['issues'].append(message)
    def save():
        p = out/'progress.json.tmp'; p.write_text(json.dumps(report,indent=2)+'\n'); p.replace(out/'progress.json')
    def local(p):
        return str(p).replace(str(ROOT),'${PROJECT_ROOT}').replace('/home/taolei/DSAA5012-Repro','${ORIGINAL_PROJECT_ROOT}')
    check(read(ROOT/'results/full-workflow-001/status.json')['status']=='complete','Workflow not complete')
    inputs = {}; binaries = {}; records = []; refs = {}; trial_counts = collections.Counter(); plans = 0
    registry = read(ROOT/'configs/full-datasets.json')
    for name,spec in registry.items():
        if not spec.get('existing_result'): continue
        folder = ROOT/'results'/spec['existing_result']; meta = read(folder/'metadata.json'); summary = read(folder/'summary.json')
        refs[name] = summary['core_sha256']
        for row in read(folder/'validation.json'):
            records.append((folder/'validation.json',dict(row,dataset=name),refs[name]))
        for row in map(json.loads,(folder/'runs.jsonl').read_text().splitlines()):
            trial_counts[row['status']]+=1
        check(meta['repetitions']==3 and meta['timeout_s']==21600,'Old protocol mismatch: '+name)
        check(meta['memory_limit_gib']==(128 if name=='AM' else 32),'Old memory cap mismatch: '+name)
        for b,sha in meta['binary_sha256'].items(): binaries[str(ROOT/'build/drivers'/b)]=sha
        plans += len(meta['methods'])*3
    for suite in SUITES:
        folder = ROOT/'results'/suite; meta = read(folder/'metadata.json')
        check(read(folder/'running.json')['status']=='complete','Suite not complete: '+suite)
        check(meta['timeout_s']==21600 and meta['memory_gib']==500 and meta['seed']==5012,'Suite protocol mismatch: '+suite)
        source_actual = digest(ROOT/'scripts/run_extended_suite.py')
        report['runner_sources'].append({'suite':suite,'expected':meta['source_sha256'],'actual':source_actual})
        check(source_actual==meta['source_sha256'],'Runner source changed: '+suite)
        for b,sha in meta['binary_sha256'].items():
            p=str(ROOT/b); check(p not in binaries or binaries[p]==sha,'Conflicting binary hash: '+b); binaries[p]=sha
        for name,spec in meta['datasets'].items():
            p=spec['path']; expected=spec['processed']['sha256']; size=spec['processed']['bytes']
            check(p not in inputs or inputs[p]==(expected,size),'Conflicting input hash: '+name); inputs[p]=(expected,size)
        for p in folder.glob('reference-*.json'):
            row=read(p)
            if row['status']=='ok': refs[row['dataset']]=row['core_sha256']
        plan={(s['dataset'],s['family'],str(s['argument'])):s['repeats'] for s in meta['plan']}; got=collections.defaultdict(list)
        plans += sum(plan.values())
        for p in folder.glob('*.json'):
            row=read(p)
            if 'label' not in row or 'repeat' not in row: continue
            check(row['input_sha256']==meta['datasets'][row['dataset']]['processed']['sha256'],'Input metadata mismatch: '+p.name)
            check(row['binary_sha256'] in meta['binary_sha256'].values(),'Unknown binary hash: '+p.name)
            if row['repeat']>0:
                key=(row['dataset'],row['label'].split('-')[0],str(row['argument'])); got[key].append(row['repeat']); trial_counts[row['status']]+=1
                if row['status']!='ok':
                    stem=row.get('reused_attempt',row['label']); logs=[folder/(stem+x) for x in ['.log','.time.txt']]
                    check(all(x.is_file() and x.stat().st_size>0 for x in logs),'Missing failure evidence: '+p.name)
                    report['failure_records'].append({'record':local(p),'status':row['status'],'exit_code':row['exit_code'],'sha256':digest(p),'reused_attempt':row.get('reused_attempt')})
            if row['status']=='ok' and row.get('exported_cores'): records.append((p,row,refs.get(row['dataset'])))
        check(set(got)==set(plan),'Group coverage mismatch: '+suite)
        for key,n in plan.items(): check(sorted(got[key])==list(range(1,n+1)),'Repeat coverage mismatch: '+repr(key))
    check(plans==405 and sum(trial_counts.values())==405,'Expected 405 terminal records')
    report['trial_status_counts']=dict(trial_counts); report['planned_records']=plans
    for p,row,reference in records:
        csv=Path(row['command'][-1]); exists=csv.is_file()
        check(row.get('core_sha256')==reference and reference is not None,'Full core hash mismatch: '+local(p))
        check(exists and csv.stat().st_size>0,'Missing validated core CSV: '+local(csv))
        report['full_core_records'].append({'record':local(p),'dataset':row['dataset'],'method':row.get('method',row.get('argument')),
            'label':row.get('label',row.get('run')),'sha256_recorded_at_execution':row.get('core_sha256'),
            'matches_reference':row.get('core_sha256')==reference,'csv':local(csv),'csv_bytes':csv.stat().st_size if exists else None})
    report['core_audit_scope']='All execution-time full-output SHA records compared with references; CSV existence/size checked. Core CSV contents were not rehashed a second time.'
    save()
    for kind,items in [('binaries',binaries),('inputs',inputs)]:
        for path,value in sorted(items.items()):
            p=Path(path); expected,size=value if kind=='inputs' else (value,None)
            check(p.resolve().is_relative_to(ROOT),'Path outside final project: '+str(p))
            before=p.stat(); actual=digest(p); after=p.stat()
            check((before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns),'File changed during hashing: '+str(p))
            check(actual==expected,'SHA mismatch: '+str(p)); check(size is None or after.st_size==size,'Input size mismatch: '+str(p))
            report[kind].append({'path':local(p),'expected_sha256':expected,'actual_sha256':actual,'bytes':after.st_size,'matches':actual==expected})
            save(); print(kind,local(p),actual==expected,flush=True)
    report['completed_at_utc']=now(); report['status']='passed_with_recorded_experimental_failures' if not report['issues'] else 'integrity_failed'
    save(); final.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'issues':report['issues'],'inputs':len(report['inputs']),'binaries':len(report['binaries']),'full_core_records':len(records),'trial_status_counts':dict(trial_counts)}),flush=True)
    if report['issues']: raise SystemExit(1)


if __name__=='__main__': main()
