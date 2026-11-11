#!/usr/bin/env python3
"""Resume only pending attempts under an explicit, prospective resource-policy amendment."""
import datetime,fcntl,json,os,re,resource,signal,subprocess,time,shutil
from pathlib import Path
import run_supplement as original
from benchmark import ROOT,digest,parse_author_phases
from run_extended_suite import classify_exit,parse_stats
from supplement_load_policy import POLICY,POLICY_PATH,snapshot,gate_decision,assess,node_cpus

OUT=original.OUT
PARENT=OUT.parent
now=original.now
save=original.save

def gate(label):
    good=0;previous=snapshot()
    while good<POLICY['gate_samples']:
        save(OUT/'running.json',dict(state='waiting_for_local_resources',label=label,
             consecutive_good=good,pid=os.getpid(),updated_at=now(),load_policy_id=POLICY['id']))
        time.sleep(POLICY['sample_interval_seconds']);current=snapshot();decision=gate_decision(previous,current)
        good=good+1 if decision['accepted'] else 0
        with (OUT/'gate-samples-v2.jsonl').open('a') as f:
            f.write(json.dumps(dict(current,at=now(),label=label,load_policy_id=POLICY['id'],**decision))+'\n')
        previous=current
    return current

def invoke(item):
    label=item['label'];record=OUT/(label+'.json')
    if record.exists():return json.loads(record.read_text())
    if (OUT/(label+'.log')).exists():raise RuntimeError('Interrupted evidence retained: '+label)
    d=item['dataset'];directory=original.REG[d]['directory'] if d in original.REG else 'synthetic-'+d
    path=ROOT/'data/processed'/directory/'author-input.hyp_sorted_by_edge_desc_node_asc.txt'
    expected=original.EXPECTED[d]['manifest']['processed'];actual=digest(path)
    if actual!=expected['sha256']:raise RuntimeError('Historical input SHA mismatch '+d)
    if shutil.disk_usage(ROOT).free<expected['vertices']*30+10*1024**3:raise RuntimeError('Insufficient output space')
    variant=item['variant'];core=OUT/(label+'.cores.csv')
    if variant=='plain':binary=ROOT/'build/drivers/sigmod';args=[str(path),item['argument'],str(core)]
    else:
        binary=ROOT/('build/extended/sigmod_extended' if variant=='chrono' else 'build/supplement-20261110/sigmod_tsc')
        args=[str(path),'stats','0','3000',str(core)]
    env=dict(os.environ,OMP_NUM_THREADS='1',OMP_DYNAMIC='FALSE',LC_ALL='C',
             REPRO_TIMER_STRIDE='32' if variant=='tsc_sample32' else '1',REPRO_TIMER_SEED=str(5012+item['repeat']))
    command=['/usr/bin/time','-v','-o',str(OUT/(label+'.time.txt')),'timeout','--signal=TERM','--kill-after=30s','21600s','taskset','-c','0',str(binary),*args]
    before=gate(label);start=time.monotonic();monitor=[]
    def limit():
        resource.setrlimit(resource.RLIMIT_AS,(500*1024**3,500*1024**3));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    with (OUT/(label+'.log')).open('x') as output:
        p=subprocess.Popen(command,stdout=output,stderr=subprocess.STDOUT,env=env,preexec_fn=limit,start_new_session=True)
        save(OUT/'running.json',dict(item,state='running',pid=p.pid,coordinator_pid=os.getpid(),started_at=now(),command=command,load_policy_id=POLICY['id']))
        try:
            while p.poll() is None:
                sample=dict(snapshot(p.pid),at=now());monitor.append(sample)
                with (OUT/(label+'.monitor.jsonl')).open('a') as f:f.write(json.dumps(sample)+'\n')
                try:p.wait(timeout=POLICY['sample_interval_seconds'])
                except subprocess.TimeoutExpired:pass
        except BaseException:os.killpg(p.pid,signal.SIGTERM);p.wait();raise
    elapsed=time.monotonic()-start;monitor.append(dict(snapshot(),at=now()))
    with (OUT/(label+'.monitor.jsonl')).open('a') as f:f.write(json.dumps(monitor[-1])+'\n')
    log=(OUT/(label+'.log')).read_text();status=classify_exit(p.returncode,elapsed,21600,log,True)
    q=dict(item,status=status,exit_code=p.returncode,process_wall_s=elapsed,input_sha256=actual,
           binary_sha256=digest(binary),command=command,environment={k:env[k] for k in ['OMP_NUM_THREADS','REPRO_TIMER_STRIDE','REPRO_TIMER_SEED']},
           started_environment=before,finished_at=now(),timeout_s=21600,memory_limit_bytes=500*1024**3,
           core_export_requested=True,core_exported=status=='ok' and core.exists(),load_policy_id=POLICY['id'],
           load_policy_sha256=digest(POLICY_PATH),runner_source_sha256=digest(Path(__file__)),**assess(before,monitor,elapsed))
    if status=='ok':
        q.update(parse_author_phases(log));q.update(parse_stats(log) if variant!='plain' else {})
        q['core_sha256']=digest(core);q['historical_core_match']=q['core_sha256'] in original.EXPECTED[d]['core_sha256_values']
        if not q['historical_core_match']:q['status']='incorrect'
        timers=[json.loads(x.split(' ',1)[1]) for x in log.splitlines() if x.startswith('SUPPLEMENT_TIMER ')]
        if timers:q['timer']=timers[-1]
        if 'decide_time_s' in q and 'compute_time_s' in q:q['D_over_CplusD']=q['decide_time_s']/(q['decide_time_s']+q['compute_time_s'])
    text=(OUT/(label+'.time.txt')).read_text();m=re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)',text)
    q['peak_rss_kib']=int(m.group(1)) if m else None;q['log_sha256']=digest(OUT/(label+'.log'));save(record,q)
    print(label,q['status'],q.get('reported_execution_s'),q['load_control_reasons'],flush=True)
    if q['status']=='incorrect':raise RuntimeError('Whole-output mismatch '+label)
    return q

def main():
    if os.environ.get('TMPDIR')!=str(ROOT/'.runtime/tmp') or ROOT.stat().st_dev==Path('/').stat().st_dev:raise RuntimeError('Guard required')
    lock=(OUT/'runner.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (Path('/sys/devices/system/cpu/cpu0/topology/thread_siblings_list').read_text().strip()!='0,64' or len(node_cpus())!=64):raise RuntimeError('CPU topology changed')
    old=json.loads((OUT/'metadata.json').read_text());handoff=json.loads((PARENT/'policy-v2-handoff/receipt.json').read_text())
    assert digest(Path(original.__file__))==old['source_sha256'],'Original runner changed'
    for name,sha in old['binary_sha256'].items():assert digest(ROOT/name)==sha,'Binary changed: '+name
    for name,sha in handoff['completed_record_sha256'].items():assert digest(OUT/name)==sha,'Old record changed: '+name
    pending=[item for item in old['plan'] if not (OUT/(item['label']+'.json')).exists()]
    assert [p['label'] for p in pending]==handoff['pending_labels'],'Handoff checkpoint changed'
    metadata={'created_at':now(),'policy':POLICY,'policy_sha256':digest(POLICY_PATH),
              'source_sha256':digest(Path(__file__)),'policy_module_sha256':digest(ROOT/'scripts/supplement_load_policy.py'),
              'original_metadata_sha256':digest(OUT/'metadata.json'),'handoff_receipt_sha256':digest(PARENT/'policy-v2-handoff/receipt.json'),
              'pending_plan':pending,'all_attempts_total':len(old['plan']),'note':'Prospective amendment only. No old row is rewritten or reclassified; mixed-policy comparisons are flagged.'}
    target=OUT/'metadata-v2.json'
    if target.exists():raise RuntimeError('Existing v2 launch requires checkpoint review')
    save(target,metadata);(OUT/'runner.pid').write_text(str(os.getpid())+'\n')
    def stop(s,f):raise InterruptedError('signal '+str(s))
    signal.signal(signal.SIGTERM,stop)
    try:
        for item in pending:invoke(item)
        save(OUT/'running.json',{'state':'complete','updated_at':now(),'records':len(old['plan']),'load_policy_id':POLICY['id'],'note':'All attempts terminated; policy-aware audit required.'})
    except BaseException as e:
        save(OUT/'running.json',{'state':'needs_attention','updated_at':now(),'error':repr(e),'load_policy_id':POLICY['id']});raise
if __name__=='__main__':main()
