#!/usr/bin/env python3
"""Switch at a verified idle boundary without interrupting a timed attempt."""
import fcntl,json,os,signal,subprocess,time
from pathlib import Path
from benchmark import ROOT,digest
from run_supplement import now,save
OUT=ROOT/'results/supplement-20261110'
E=OUT/'experiments'
DEST=OUT/'policy-v2-handoff'

def process(pid):
    try:
        p=Path('/proc')/str(pid);raw=(p/'stat').read_text();fields=raw[raw.rfind(')')+2:].split()
        return {'state':fields[0],'start_ticks':fields[19],
                'cmdline':(p/'cmdline').read_bytes().decode().split('\0'),
                'children':(p/'task'/str(pid)/'children').read_text().split()}
    except FileNotFoundError:return None

def main():
    if os.environ.get('TMPDIR')!=str(ROOT/'.runtime/tmp') or ROOT.stat().st_dev==Path('/').stat().st_dev:raise RuntimeError('Guard required')
    lock=(OUT/'policy-handoff.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    DEST.mkdir(exist_ok=False);save(DEST/'controller.json',{'pid':os.getpid(),'started_at':now(),'state':'waiting_for_idle_boundary'})
    runner=int((E/'runner.pid').read_text());coordinator=int((OUT/'workflow.pid').read_text())
    identity=process(runner);parent=process(coordinator)
    assert identity and any(x.endswith('/run_supplement.py') for x in identity['cmdline']),identity
    assert parent and any(x.endswith('/continue_supplement.py') for x in parent['cmdline']),parent
    frozen=False
    try:
        while True:
            state=json.loads((E/'running.json').read_text());current=process(runner)
            if not current or current['start_ticks']!=identity['start_ticks']:raise RuntimeError('Original runner exited or changed before handoff')
            if state.get('state')=='needs_attention':raise RuntimeError('Original runner needs independent inspection')
            if state.get('state')!='waiting_for_low_load':time.sleep(2);continue
            os.kill(runner,signal.SIGSTOP);frozen=True
            for _ in range(50):
                current=process(runner)
                if current and current['state'] in ['T','t']:break
                time.sleep(.02)
            state=json.loads((E/'running.json').read_text());current=process(runner)
            if not current or current['state'] not in ['T','t']:raise RuntimeError('Could not freeze coordinator at boundary')
            if state.get('state')!='waiting_for_low_load' or current['children']:
                os.kill(runner,signal.SIGCONT);frozen=False;time.sleep(2);continue
            # A frozen idle runner with no children cannot start a new attempt.
            for name,p in [('status-before.json',OUT/'status.json'),('running-before.json',E/'running.json'),('metadata-v1.json',E/'metadata.json'),('formal-log-before.txt',OUT/'formal-supplements.log')]:
                (DEST/name).write_bytes(p.read_bytes())
            metadata=json.loads((E/'metadata.json').read_text());completed={};pending=[]
            for item in metadata['plan']:
                name=item['label']+'.json';p=E/name
                if p.exists():completed[name]=digest(p)
                else:
                    if (E/(item['label']+'.log')).exists():raise RuntimeError('Pending attempt has partial evidence: '+item['label'])
                    pending.append(item['label'])
            receipt={'authorized_reason':'User requested a reasonable resource gate using idle CPUs while preserving comparability.',
                     'switched_at':now(),'old_runner_pid':runner,'old_coordinator_pid':coordinator,
                     'boundary':state,'no_timed_process_interrupted':True,'old_runner_identity':identity,
                     'completed_record_sha256':completed,'pending_labels':pending,'total_planned':len(metadata['plan']),
                     'project_device':ROOT.stat().st_dev,'root_device':Path('/').stat().st_dev}
            save(DEST/'receipt.json',receipt)
            os.kill(runner,signal.SIGTERM);os.kill(runner,signal.SIGCONT);frozen=False
            break
    finally:
        if frozen:os.kill(runner,signal.SIGCONT)
    for _ in range(100):
        live=[]
        for pid in [runner,coordinator]:
            info=process(pid)
            if info and info['state']!='Z':live.append(pid)
        if not live:break
        time.sleep(.2)
    else:raise RuntimeError('Old coordinator did not exit cleanly; no new launch')
    for name,p in [('status-after.json',OUT/'status.json'),('running-after.json',E/'running.json'),('formal-log-after.txt',OUT/'formal-supplements.log'),('continuation-log-after.txt',OUT/'continuation-launch.log')]:
        (DEST/name).write_bytes(p.read_bytes())
    for name in ['runner.lock']:
        with (E/name).open('a') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
    with (OUT/'workflow.lock').open('a') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
    with (OUT/'continuation-v2-launch.log').open('x') as log:
        child=subprocess.Popen(['python3','-B','scripts/continue_supplement_v2.py'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    save(DEST/'controller.json',{'pid':os.getpid(),'completed_at':now(),'state':'new_coordinator_launched','new_pid':child.pid,'completed_records':len(completed),'pending_records':len(pending)})
    print('Boundary handoff complete; new coordinator',child.pid,'pending',len(pending),flush=True)
if __name__=='__main__':
    try:main()
    except BaseException as exc:
        if DEST.exists():save(DEST/'error.json',{'error':repr(exc),'at':now()})
        raise
