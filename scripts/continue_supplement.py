#!/usr/bin/env python3
"""Wait for verified restoration, validate supplemental builds, then run the new study."""
from pathlib import Path
import os,json,fcntl,time,subprocess,signal,datetime
from benchmark import ROOT,digest
OUT=ROOT/'results/supplement-20261110'
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(p,q):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(q,indent=2)+'\n');t.replace(p)
def main():
 if os.environ.get('TMPDIR')!=str(ROOT/'.runtime/tmp'):raise RuntimeError('Guard required')
 OUT.mkdir(parents=True,exist_ok=True);lock=(OUT/'workflow.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);(OUT/'workflow.pid').write_text(str(os.getpid())+'\n')
 while True:
  f=OUT/'restore/status.json';s=json.loads(f.read_text()) if f.exists() else {}
  if s.get('state')=='complete':break
  if s.get('state')=='needs_attention':raise RuntimeError('Restoration needs attention: '+str(s))
  pidfile=OUT/'restore/workflow.pid'
  if pidfile.exists() and not Path('/proc/'+pidfile.read_text().strip()).exists():raise RuntimeError('Restore process ended without completion')
  save(OUT/'status.json',{'state':'waiting_for_input_restoration','restore_step':s.get('step'),'pid':os.getpid(),'updated_at':now()});time.sleep(20)
 steps=[('build',['python3','scripts/build_supplement.py']),('small-validation',['python3','scripts/check_supplement.py']),('tas-canonicalization',['python3','scripts/prepare_tas_check.py']),('soa-scale-inputs',['python3','scripts/prepare_full_inputs.py','scales','SOA']),('soa-work-counts',['python3','scripts/profile_soa.py']),('formal-supplements',['python3','scripts/run_supplement.py']),('audit',['python3','scripts/audit_supplement.py'])]
 for name,cmd in steps:
  if (OUT/(name+'.complete.json')).exists():continue
  if (OUT/(name+'.log')).exists():raise RuntimeError('Uncompleted stage log retained; inspect before retry: '+name)
  save(OUT/'status.json',{'state':'running','step':name,'pid':os.getpid(),'command':cmd,'updated_at':now()})
  with (OUT/(name+'.log')).open('x') as log:
   p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   try:code=p.wait()
   except BaseException:os.killpg(p.pid,signal.SIGTERM);p.wait();raise
  if code:raise RuntimeError('Stage failed '+name+' code='+str(code))
  save(OUT/(name+'.complete.json'),{'completed_at':now(),'step':name})
 save(OUT/'status.json',{'state':'audited_pending_report','updated_at':now(),'note':'Integrity audit ended; interpret calibration quality flags before updating reports. TAS independent identity still requires external script/hash.'})
if __name__=='__main__':
 try:main()
 except BaseException as e:
  if OUT.exists():save(OUT/'status.json',{'state':'needs_attention','error':repr(e),'updated_at':now()})
  raise
