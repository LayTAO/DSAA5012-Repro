#!/usr/bin/env python3
"""Checkpointed, sequential supplementary experiments; frozen original evidence stays separate."""
import os,json,time,re,resource,subprocess,signal,fcntl,random,hashlib,datetime,statistics,shutil
from pathlib import Path
from benchmark import ROOT,digest,parse_author_phases
from run_extended_suite import parse_stats,classify_exit
OUT=ROOT/'results/supplement-20261110/experiments'
EXPECTED=json.loads((ROOT/'configs/supplement-expected.json').read_text())
REG=json.loads((ROOT/'configs/full-datasets.json').read_text())
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(p,x):
 t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(x,indent=2)+'\n');t.replace(p)
def cpu_read():
 rows={}
 for line in Path('/proc/stat').read_text().splitlines():
  z=line.split()
  if z and z[0] in ['cpu0','cpu64']:
   n=list(map(int,z[1:9]));rows[z[0]]={'total':sum(n),'idle':n[3]+n[4]}
 return rows
def usage(a,b,k):
 n=b[k]['total']-a[k]['total'];return (1-(b[k]['idle']-a[k]['idle'])/n)*100 if n else 0
def snapshot():return {'at':now(),'load':os.getloadavg(),'cpu':cpu_read(),'memavailable_kib':int(re.search(r'MemAvailable:\s+(\d+)',Path('/proc/meminfo').read_text()).group(1))}
def gate(label):
 # A priori gates; no completed run is deleted or selected by elapsed time.
 good=0;history=OUT/'gate-samples.jsonl';previous=snapshot()
 while good<3:
  save(OUT/'running.json',{'state':'waiting_for_low_load','label':label,'consecutive_good':good,'pid':os.getpid(),'updated_at':now()})
  time.sleep(5);x=snapshot();u0=usage(previous['cpu'],x['cpu'],'cpu0');u64=usage(previous['cpu'],x['cpu'],'cpu64')
  ok=x['load'][0]<=8 and u0<=10 and u64<=10 and x['memavailable_kib']>532*1024**2
  good=good+1 if ok else 0
  with history.open('a') as f:f.write(json.dumps(dict(x,label=label,cpu0_busy_pct=u0,cpu64_busy_pct=u64,accepted=ok))+'\n')
  previous=x
 return x
def invoke(item):
 label=item['label'];record=OUT/(label+'.json')
 if record.exists():
  q=json.loads(record.read_text());return q
 if (OUT/(label+'.log')).exists():raise RuntimeError('Interrupted attempt preserved; inspect before rerun: '+label)
 d=item['dataset'];directory=REG[d]['directory'] if d in REG else 'synthetic-'+d
 path=ROOT/'data/processed'/directory/'author-input.hyp_sorted_by_edge_desc_node_asc.txt'
 expected=EXPECTED[d]['manifest']['processed'];actual=digest(path)
 if actual!=expected['sha256']:raise RuntimeError('Historical input SHA mismatch: '+d)
 if shutil.disk_usage(ROOT).free < expected['vertices']*30+10*1024**3:raise RuntimeError('Insufficient free space for complete core output: '+d)
 variant=item['variant'];a=item.get('argument','0');core=OUT/(label+'.cores.csv')
 if variant=='plain':binary=ROOT/'build/drivers/sigmod';args=[str(path),a,str(core)]
 elif variant=='chrono':binary=ROOT/'build/extended/sigmod_extended';args=[str(path),'stats','0','3000',str(core)]
 else:binary=ROOT/'build/supplement-20261110/sigmod_tsc';args=[str(path),'stats','0','3000',str(core)]
 env=dict(os.environ,OMP_NUM_THREADS='1',OMP_DYNAMIC='FALSE',LC_ALL='C',REPRO_TIMER_STRIDE='32' if variant=='tsc_sample32' else '1',REPRO_TIMER_SEED=str(5012+item['repeat']))
 command=['/usr/bin/time','-v','-o',str(OUT/(label+'.time.txt')),'timeout','--signal=TERM','--kill-after=30s','21600s','taskset','-c','0',str(binary),*args]
 before=gate(label);start=time.monotonic();monitor=[]
 def limit():resource.setrlimit(resource.RLIMIT_AS,(500*1024**3,500*1024**3));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
 with (OUT/(label+'.log')).open('x') as output:
  p=subprocess.Popen(command,stdout=output,stderr=subprocess.STDOUT,env=env,preexec_fn=limit,start_new_session=True)
  save(OUT/'running.json',dict(item,state='running',pid=p.pid,coordinator_pid=os.getpid(),started_at=now(),command=command))
  try:
   while p.poll() is None:
    x=snapshot();monitor.append(x)
    with (OUT/(label+'.monitor.jsonl')).open('a') as f:f.write(json.dumps(x)+'\n')
    try:p.wait(timeout=5)
    except subprocess.TimeoutExpired:pass
  except BaseException:os.killpg(p.pid,signal.SIGTERM);p.wait();raise
 elapsed=time.monotonic()-start;log=(OUT/(label+'.log')).read_text();status=classify_exit(p.returncode,elapsed,21600,log,True)
 monitor.append(snapshot())
 with (OUT/(label+'.monitor.jsonl')).open('a') as f:f.write(json.dumps(monitor[-1])+'\n')
 q=dict(item,status=status,exit_code=p.returncode,process_wall_s=elapsed,input_sha256=actual,binary_sha256=digest(binary),command=command,environment={k:env[k] for k in ['OMP_NUM_THREADS','REPRO_TIMER_STRIDE','REPRO_TIMER_SEED']},started_environment=before,finished_at=now(),timeout_s=21600,memory_limit_bytes=500*1024**3,core_export_requested=True,core_exported=status=='ok' and core.exists(),load_max=max(x['load'][0] for x in monitor),load_control_pass=all(x['load'][0]<=8 for x in monitor))
 sibling=[usage(x['cpu'],y['cpu'],'cpu64') for x,y in zip([before,*monitor],monitor)]
 q['sibling_busy_max_pct']=max(sibling,default=0);q['load_control_pass'] &= q['sibling_busy_max_pct']<=10
 if status=='ok':
  q.update(parse_author_phases(log));q.update(parse_stats(log) if variant!='plain' else {})
  q['core_sha256']=digest(core);q['historical_core_match']=q['core_sha256'] in EXPECTED[d]['core_sha256_values']
  if not q['historical_core_match']:q['status']='incorrect'
  timer=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith('SUPPLEMENT_TIMER ')]
  if timer:q['timer']=timer[-1]
  if 'decide_time_s' in q and 'compute_time_s' in q:q['D_over_CplusD']=q['decide_time_s']/(q['decide_time_s']+q['compute_time_s'])
 q['log_sha256']=digest(OUT/(label+'.log'))
 text=(OUT/(label+'.time.txt')).read_text();m=re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)',text);q['peak_rss_kib']=int(m.group(1)) if m else None
 save(record,q);print(label,q['status'],q.get('reported_execution_s'),flush=True)
 if q['status']=='incorrect':raise RuntimeError('Whole-output mismatch: '+label)
 return q

def main():
 if os.environ.get('TMPDIR')!=str(ROOT/'.runtime/tmp') or ROOT.stat().st_dev==Path('/').stat().st_dev:raise RuntimeError('Guard required')
 OUT.mkdir(parents=True,exist_ok=True);lock=(OUT/'runner.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);(OUT/'runner.pid').write_text(str(os.getpid())+'\n')
 flags=Path('/proc/cpuinfo').read_text()
 if any(x not in flags for x in ['constant_tsc','nonstop_tsc','rdtscp']):raise RuntimeError('Invariant TSC prerequisites missing')
 plan=[];rng=random.Random(5012)
 # Interleave all instrumentation variants within each repetition, keeping all attempts.
 for d in ['HI','CO','GE','DB','DF','THS','AM','TAS','AMZ','SOA','POW-S-approx']:
  for repeat in range(1,4):
   variants=['plain','chrono','tsc_full','tsc_sample32'];rng.shuffle(variants)
   for variant in variants:plan.append(dict(label=f'timer-{d}-{variant}-r{repeat}',study='timer',dataset=d,variant=variant,argument='0',repeat=repeat))
 methods=['0','1','2'];rng.shuffle(methods)
 for repeat in range(1,4):
  order=methods[repeat-1:]+methods[:repeat-1]
  for a in order:plan.append(dict(label=f'pows-ablation-{a}-r{repeat}',study='pows_ablation',dataset='POW-S-approx',variant='plain',argument=a,repeat=repeat))
 metadata={'created_at':now(),'source_sha256':digest(Path(__file__)),'binary_sha256':{str(p.relative_to(ROOT)):digest(p) for p in [ROOT/'build/drivers/sigmod',ROOT/'build/extended/sigmod_extended',ROOT/'build/supplement-20261110/sigmod_tsc']},'plan':plan,'input_policy':'Exact historical processed SHA required','repeats':3,'timeout_s':21600,'memory_gib':500,'cpu':0,'sibling_cpu':64,'load_gate':'3 consecutive 5-second samples: load1<=8, cpu0 and cpu64 busy<=10%, MemAvailable>532GiB','quality_policy':'All attempts retained; load gate violations flagged, never deleted. Timing calibration not declared adequate solely by denominator correction.','timer_acceptance':'Candidate only if all three complete/core-match/load-clean, mean instrumented/plain execution ratio in [0.90,1.10], TSC spread <=0.5%, zero migrations, and at least 100 samples for both regions per run. Raw/empty-pair-adjusted results both retained; calibration does not prove no perturbation.'}
 mp=OUT/'metadata.json'
 if mp.exists():
  old=json.loads(mp.read_text());assert old['plan']==plan and old['source_sha256']==metadata['source_sha256'] and old['binary_sha256']==metadata['binary_sha256'],'Resume config changed'
 else:save(mp,metadata)
 def stop(s,f):raise InterruptedError('signal '+str(s))
 signal.signal(signal.SIGTERM,stop)
 try:
  if not (OUT/'timer-calibration.json').exists():
   gate('timer-calibration');cmd=['taskset','-c','0',str(ROOT/'build/supplement-20261110/timer_calibration')]
   p=subprocess.run(cmd,capture_output=True,text=True,check=True);(OUT/'timer-calibration.log').write_text(p.stdout+p.stderr)
   save(OUT/'timer-calibration.json',{'at':now(),'command':cmd,'clocksource':Path('/sys/devices/system/clocksource/clocksource0/current_clocksource').read_text().strip(),'output':p.stdout,'binary_sha256':digest(Path(cmd[-1]))})
  for item in plan:invoke(item)
  save(OUT/'running.json',{'state':'complete','updated_at':now(),'records':len(plan),'note':'Formal attempts ended; quality flags and calibration acceptance require audit.'})
 except BaseException as e:save(OUT/'running.json',{'state':'needs_attention','updated_at':now(),'error':repr(e)});raise
if __name__=='__main__':main()
