#!/usr/bin/env python3
"""Restore only supplementary-study inputs; verify every recovered historical identity."""
from pathlib import Path
import os,json,subprocess,fcntl,datetime,resource,signal
from benchmark import ROOT,digest
OUT=ROOT/'results/supplement-20261110/restore'
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(name,row):
 p=OUT/name;t=p.with_suffix('.tmp');t.write_text(json.dumps(row,indent=2)+'\n');t.replace(p)
def main():
 if os.environ.get('TMPDIR')!=str(ROOT/'.runtime/tmp') or ROOT.stat().st_dev==Path('/').stat().st_dev:raise RuntimeError('Guard required')
 OUT.mkdir(parents=True,exist_ok=True)
 (ROOT/'data/processed').mkdir(parents=True,exist_ok=True)
 lock=(OUT/'workflow.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 (OUT/'workflow.pid').write_text(str(os.getpid())+'\n')
 expected=json.loads((ROOT/'configs/supplement-expected.json').read_text())
 registry=json.loads((ROOT/'configs/full-datasets.json').read_text())
 steps=[('upstream',['python3','scripts/fetch_upstream.py'],None),('native',['bash','scripts/build_native.sh'],None),('drivers',['bash','scripts/build_drivers.sh'],None),('extended',['bash','scripts/build_extended.sh'],None),('data-tools',['bash','scripts/build_data_tools.sh'],None),('baseline-archive',['python3','scripts/fetch_data.py','baseline'],None)]
 for d in ['HI','CO','GE','DB','DF','THS','AM','TAS','AMZ','SOA']:
  if d in ['THS','TAS','SOA','AMZ']:steps.append(('download-'+d,['python3','scripts/fetch_extended_data.py',d],None))
  script='prepare_author_data.py' if d in ['CO','DB','AM'] else 'prepare_extended_data.py' if d in ['THS','TAS','SOA','AMZ'] else 'prepare_cornell.py'
  steps.append(('prepare-'+d,['python3','scripts/'+script,d],d))
 steps.append(('prepare-POW-S',['python3','scripts/prepare_full_inputs.py','synthetic','POW-S-approx'],'POW-S-approx'))
 def limit():resource.setrlimit(resource.RLIMIT_AS,(500*1024**3,500*1024**3));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
 for name,cmd,d in steps:
  if (OUT/(name+'.complete.json')).exists():continue
  if (OUT/(name+'.log')).exists():raise RuntimeError('Uncompleted stage has existing evidence; inspect before retry: '+name)
  save('status.json',{'state':'running','step':name,'pid':os.getpid(),'updated_at':now(),'command':cmd})
  try:
   with (OUT/(name+'.log')).open('x') as log:
    p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=limit)
    try:code=p.wait()
    except BaseException:os.killpg(p.pid,signal.SIGTERM);p.wait();raise
   if code:raise RuntimeError('Command failed: '+str(code))
   result={'step':name,'completed_at':now()}
   if d:
    dirname=registry[d]['directory'] if d in registry else 'synthetic-'+d
    manifest=json.loads((ROOT/'data/processed'/dirname/'manifest.json').read_text())
    old=expected[d]['manifest']['processed'];new=manifest['processed']
    for k in ['sha256','vertices','edges']:
     if new[k]!=old[k]:raise RuntimeError(f'Restored {d} {k} differs: {new[k]} != {old[k]}')
    result.update(dataset=d,input_sha256=new['sha256'],historical_identity_matched=True)
   save(name+'.complete.json',result)
  except BaseException as e:
   save('status.json',{'state':'needs_attention','step':name,'error':repr(e),'updated_at':now()});raise
 save('status.json',{'state':'complete','updated_at':now(),'datasets':11})
if __name__=='__main__':main()
