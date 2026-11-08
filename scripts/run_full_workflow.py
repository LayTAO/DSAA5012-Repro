#!/usr/bin/env python3
"""Durable, sequential full-paper workflow; all writes inherit the storage guard."""
import datetime
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
from benchmark import ROOT,digest


def main():
    if os.environ.get('TMPDIR')!=str(ROOT/'.runtime/tmp'):raise RuntimeError('Use run_on_server.sh')
    out=ROOT/'results/full-workflow-001';out.mkdir(parents=True,exist_ok=True)
    lock=(out/'workflow.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    steps=[
        ('scale-inputs',['python3','scripts/prepare_full_inputs.py','scales','AMZ','TAS','SOA','AM']),
        ('real-experiments',['python3','scripts/run_extended_suite.py','--phase','real','--run-id','001']),
        ('synthetic-small-input',['python3','scripts/prepare_full_inputs.py','synthetic','POW-S-approx']),
        ('synthetic-small-experiments',['python3','scripts/run_extended_suite.py','--phase','synthetic','--datasets','POW-S-approx','--run-id','small001']),
        ('synthetic-large-input',['python3','scripts/prepare_full_inputs.py','synthetic','POW-L-approx']),
        ('synthetic-large-experiments',['python3','scripts/run_extended_suite.py','--phase','synthetic','--datasets','POW-L-approx','--run-id','large001'])]
    def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
    def save(name,value):
        path=out/name;temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value,indent=2)+'\n');temporary.replace(path)
    metadata={'steps':steps,'root':str(ROOT),'created_at_utc':now(),'workflow_sha256':digest(Path(__file__)),
              'storage_device':ROOT.stat().st_dev,'root_device':Path('/').stat().st_dev}
    if metadata['storage_device']==metadata['root_device']:raise RuntimeError('Root filesystem refused')
    if (out/'metadata.json').exists():
        old=json.loads((out/'metadata.json').read_text())
        if old['workflow_sha256']!=metadata['workflow_sha256']:raise RuntimeError('Workflow changed; inspect before resuming')
    else:save('metadata.json',metadata)
    def terminate(signum,frame):raise InterruptedError('Signal '+str(signum))
    signal.signal(signal.SIGTERM,terminate)
    for name,command in steps:
        complete=out/(name+'.complete.json')
        if complete.exists():continue
        save('status.json',{'status':'running','step':name,'command':command,'updated_at':now(),'pid':os.getpid()})
        print(now(),name,flush=True)
        try:
            with (out/(name+'.log')).open('a') as log:
                process=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                try:code=process.wait()
                except BaseException:
                    os.killpg(process.pid,signal.SIGTERM);process.wait();raise
            if code:raise RuntimeError('Step exit status '+str(code))
            save(complete.name,{'step':name,'completed_at_utc':now()})
        except BaseException as error:
            save('status.json',{'status':'needs_attention','step':name,'error':repr(error),'updated_at':now()});raise
    save('status.json',{'status':'complete','updated_at':now(),'note':'Experiments have ended; failed/time-limited trials remain explicit in suite summaries.'})

if __name__=='__main__':main()
