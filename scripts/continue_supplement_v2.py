#!/usr/bin/env python3
"""New coordinator, preserving every old coordinator log and record."""
import fcntl,json,os,signal,subprocess
from pathlib import Path
from benchmark import ROOT
from run_supplement import now,save
OUT=ROOT/'results/supplement-20261110'
def main():
    if os.environ.get('TMPDIR')!=str(ROOT/'.runtime/tmp') or ROOT.stat().st_dev==Path('/').stat().st_dev:raise RuntimeError('Guard required')
    lock=(OUT/'workflow.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    (OUT/'workflow.pid').write_text(str(os.getpid())+'\n')
    try:
        for name,script in [('formal-supplements-v2','run_supplement_v2.py'),('audit-v2','audit_supplement_v2.py')]:
            if (OUT/(name+'.log')).exists():raise RuntimeError('Existing v2 stage evidence requires review: '+name)
            command=['python3','-B','scripts/'+script]
            save(OUT/'status.json',{'state':'running','step':name,'pid':os.getpid(),'command':command,'updated_at':now()})
            with (OUT/(name+'.log')).open('x') as log:
                p=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                try:code=p.wait()
                except BaseException:os.killpg(p.pid,signal.SIGTERM);p.wait();raise
            if code:raise RuntimeError('Stage failed '+name+' code='+str(code))
            save(OUT/(name+'.complete.json'),{'completed_at':now(),'step':name})
        save(OUT/'status.json',{'state':'audited_pending_report','updated_at':now(),'note':'Review policy cohorts and quality flags before report update.'})
    except BaseException as e:
        save(OUT/'status.json',{'state':'needs_attention','error':repr(e),'updated_at':now()});raise
if __name__=='__main__':main()
