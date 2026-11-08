#!/usr/bin/env python3
"""Resume full paper experiments with per-attempt records, failures and core validation."""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import random
import re
import resource
import signal
import shutil
import subprocess
import time
from benchmark import ROOT,digest,parse_author_phases


def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()


def classify_exit(code,elapsed,timeout,log,export=False):
    if code==0:return 'ok'
    if export and 'REPRO_METRICS ' in log:return 'export_failed'
    if code==124 or (code==137 and elapsed>=timeout):return 'timeout'
    if re.search(r'bad_alloc|cannot allocate memory|out of memory',log,re.I):return 'memory_limit'
    if 'UPSTREAM_UNSUPPORTED:' in log:return 'unsupported'
    return 'failed'


def save(path,value):
    tmp=path.with_name(path.name+'.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)


def physical_cpus():
    selected={}
    for cpu in sorted(os.sched_getaffinity(0)):
        base=Path('/sys/devices/system/cpu')/('cpu'+str(cpu))/'topology'
        key=((base/'physical_package_id').read_text().strip(),(base/'core_id').read_text().strip())
        selected.setdefault(key,cpu)
    return list(selected.values())


def parse_stats(log):
    rows=[{'iteration':int(a),'computed':int(b),'changed':int(c)} for a,b,c in re.findall(r'^(\d+),(\d+),(\d+)\s*$',log,re.M)]
    result={'iteration_trace':rows}
    for name in ['decide_time','compute_time','exc_Time']:
        match=re.findall(r'^'+name+r':\s*([\d.eE+-]+)',log,re.M)
        if match:result[name+'_s']=float(match[-1])
    if result.get('exc_Time_s',0)>0 and 'decide_time_s' in result:
        result['ruc_fraction_of_execution']=result['decide_time_s']/result['exc_Time_s']
    return result


class Suite:
    def __init__(self,out,timeout,memory_gib):
        self.out=out;self.timeout=timeout;self.memory_gib=memory_gib;self.cpus=physical_cpus();self.references={};self.checked=set()

    def verify_input(self,data):
        path=Path(data['path'])
        if str(path) not in self.checked:
            if digest(path)!=data['processed']['sha256']:raise RuntimeError('Input checksum mismatch: '+str(path))
            self.checked.add(str(path))

    def invoke(self,label,data,kind,argument,repeat,export=False):
        record=self.out/(label+'.json')
        if record.exists():return json.loads(record.read_text())
        self.verify_input(data)
        if export and shutil.disk_usage(ROOT).free<data['processed']['vertices']*30+10*1024**3:
            raise RuntimeError('Insufficient space for full core validation')
        threads=int(argument) if kind=='parallel' else 1
        if threads>len(self.cpus):raise RuntimeError('Not enough distinct physical cores')
        cores=self.cpus[:threads];csv=self.out/(label+'.cores.csv');log=self.out/(label+'.log');rss=self.out/(label+'.time.txt')
        if kind in ['stats','parallel']:
            binary=ROOT/'build/extended/sigmod_extended';parameters=[str(data['path']),kind,str(argument),'3000',str(csv) if export else '-']
        else:
            binary=ROOT/'build/drivers'/('vldb' if argument=='OPTIV' else 'sigmod')
            parameters=[str(data['path']),str(argument),str(csv) if export else '-']
        command=['/usr/bin/time','-v','-o',str(rss),'timeout','--signal=TERM','--kill-after=30s',str(self.timeout)+'s','taskset','-c',','.join(map(str,cores)),str(binary),*parameters]
        environment=dict(os.environ,OMP_NUM_THREADS=str(threads),OMP_DYNAMIC='FALSE',OMP_PLACES='cores',OMP_PROC_BIND='close',OPENBLAS_NUM_THREADS='1',LC_ALL='C')
        cap=self.memory_gib*1024**3
        def limit():resource.setrlimit(resource.RLIMIT_AS,(cap,cap))
        while True:
            available=int(re.search(r'MemAvailable:\s+(\d+)',Path('/proc/meminfo').read_text()).group(1))*1024
            if available>cap+32*1024**3:break
            save(self.out/'running.json',{'status':'waiting_for_memory','label':label,'available_bytes':available,'required_bytes':cap+32*1024**3,'updated_at':now()});time.sleep(30)
        started=time.monotonic();timestamp=now()
        with log.open('w') as output:
            process=subprocess.Popen(command,stdout=output,stderr=subprocess.STDOUT,env=environment,preexec_fn=limit,start_new_session=True)
            save(self.out/'running.json',{'status':'running','label':label,'started_at':timestamp,'pid':process.pid,'command':command})
            try:process.wait()
            except BaseException:
                os.killpg(process.pid,signal.SIGKILL);process.wait();raise
        text=log.read_text();code=process.returncode
        elapsed=time.monotonic()-started
        status=classify_exit(code,elapsed,self.timeout,text,export)
        row={'label':label,'dataset':data['dataset'],'paper_id':data['paper_id'],'kind':kind,'argument':argument,'repeat':repeat,'status':status,'exit_code':code,'recorded_at_utc':timestamp,'process_wall_s':time.monotonic()-started,'command':command,'input_sha256':data['processed']['sha256'],'binary_sha256':digest(binary),'threads':threads,'physical_cpus':cores,'memory_limit_kind':'RLIMIT_AS virtual address space; not identical to paper physical RAM limit','memory_limit_bytes':cap,'timeout_s':self.timeout,'exported_cores':export,'load_average_end':os.getloadavg()}
        if rss.exists():
            peak=re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)',rss.read_text())
            row['peak_rss_kib']=int(peak.group(1)) if peak else None
        if status=='ok':
            metrics=[line.split(' ',1)[1] for line in text.splitlines() if line.startswith('REPRO_METRICS ')]
            if len(metrics)!=1:raise RuntimeError('Missing driver metrics: '+label)
            row.update(json.loads(metrics[0]));row.update(parse_author_phases(text))
            if row['vertices']!=data['processed']['vertices']:raise RuntimeError('Vertex count mismatch: '+label)
            if export:row['core_sha256']=digest(csv)
        if kind=='stats':row.update(parse_stats(text))
        save(record,row);print(label,status,flush=True)
        return row

    def reference(self,data):
        key=data['dataset']
        if key in self.references:return self.references[key]
        if data.get('existing_result'):
            summary=json.loads((ROOT/'results'/data['existing_result']/'summary.json').read_text())
            if summary['data']['sha256']!=data['processed']['sha256']:raise RuntimeError('Old result input mismatch')
            value=summary['core_sha256']
        else:
            argument='1' if data.get('scale') else '0'
            row=self.invoke('reference-'+key,data,'core',argument,0,True)
            if row['status']!='ok':raise RuntimeError('Reference failed: '+key)
            value=row['core_sha256']
        self.references[key]=value
        return value

    def check(self,row,reference):
        if row['status']=='ok' and row.get('core_sha256')!=reference:
            row['status']='incorrect';save(self.out/(row['label']+'.json'),row)
            raise RuntimeError('Full core outputs disagree: '+row['label'])

    def series(self,item,data):
        family,argument,repeats=item['family'],item['argument'],item['repeats'];key=data['dataset']
        ref=self.reference(data);base=family+'-'+key+'-'+str(argument)
        if family=='core':
            validation=self.invoke(base+'-validation',data,'core',argument,0,True);self.check(validation,ref)
            if validation['status']=='export_failed':raise RuntimeError('Validation export failed after algorithm completion: '+base)
            for repeat in range(1,repeats+1):
                if repeat==1 and validation['status']!='ok':
                    alias=dict(validation,label=base+'-r1',repeat=1,attempt_origin='failed_validation',reused_attempt=validation['label'])
                    save(self.out/(base+'-r1.json'),alias)
                else:
                    measured=self.invoke(base+'-r'+str(repeat),data,'core',argument,repeat)
                    if measured['status']=='ok' and validation['status']!='ok':
                        validation=self.invoke(base+'-validation-retry',data,'core',argument,0,True);self.check(validation,ref)
                        if validation['status']!='ok':raise RuntimeError('Successful timing remains unvalidated: '+base)
        else:
            kind='core' if family=='scale' else family
            verified=False
            for repeat in range(1,repeats+1):
                # Concurrent schedules may vary: validate every parallel repeat.
                row=self.invoke(base+'-r'+str(repeat),data,kind,argument,repeat,family=='parallel' or not verified)
                if row.get('exported_cores') and row['status']=='ok':self.check(row,ref);verified=True
                if row['status']=='export_failed':raise RuntimeError('Core export failed: '+row['label'])


def inputs(phase,selected=None):
    registry=json.loads((ROOT/'configs/full-datasets.json').read_text()) if phase=='real' else {
        d:{'directory':'synthetic-'+d,'paper_id':d.replace('-approx',''),'existing_result':None} for d in ['POW-S-approx','POW-L-approx']}
    result={}
    if selected:registry={d:registry[d] for d in selected}
    for dataset,spec in registry.items():
        directory=ROOT/'data/processed'/spec['directory'];manifest=json.loads((directory/'manifest.json').read_text())
        result[dataset]=dict(spec,dataset=dataset,path=str(directory/'author-input.hyp_sorted_by_edge_desc_node_asc.txt'),processed=manifest['processed'],data_manifest=str(directory/'manifest.json'))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['real','synthetic'],default='real');parser.add_argument('--datasets',nargs='+')
    parser.add_argument('--families',nargs='+',default=['core','stats','parallel','scale'],choices=['core','stats','parallel','scale'])
    parser.add_argument('--run-id',default='001');parser.add_argument('--timeout',type=int,default=21600);parser.add_argument('--memory-gib',type=int,default=500)
    args=parser.parse_args()
    if not args.run_id.isalnum() or args.timeout<1 or args.memory_gib<1:parser.error('Invalid limits/run ID')
    if os.environ.get('TMPDIR')!=str(ROOT/'.runtime/tmp'):raise RuntimeError('Use guarded server environment')
    out=ROOT/'results'/('full-'+args.phase+'-'+args.run_id);out.mkdir(parents=True,exist_ok=True)
    lock=(out/'runner.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    data=inputs(args.phase,args.datasets)
    plan=[]
    for key,spec in list(data.items()):
        if 'core' in args.families and not spec.get('existing_result'):
            methods=['0','1','2','OPTIV'] if args.phase=='synthetic' else ['0','1','2','3','4','5','OPTIV']
            for method in methods:plan.append({'dataset':key,'family':'core','argument':method,'repeats':3})
        if 'stats' in args.families:
            plan.append({'dataset':key,'family':'stats','argument':'0','repeats':3})
            if key in ['DF','THS','TAS','AMZ']:
                plan.extend({'dataset':key,'family':'stats','argument':m,'repeats':1} for m in ['1','2','5'])
        if 'parallel' in args.families and key in ['AMZ','SOA','POW-L-approx']:
            plan.extend({'dataset':key,'family':'parallel','argument':str(t),'repeats':3} for t in [1,2,4,8,16,32,64])
        if 'scale' in args.families and key in ['AMZ','TAS','SOA','AM']:
            scales=json.loads((ROOT/'data/processed'/('scales-'+key)/'manifest.json').read_text())
            for fraction,entry in scales['fractions'].items():
                scale_key=key+'-E'+fraction.replace('.','p')
                data[scale_key]=dict(dataset=scale_key,paper_id=key,path=str(ROOT/entry['path']),processed=entry['processed'],scale=fraction)
                plan.append({'dataset':scale_key,'family':'scale','argument':'0','repeats':3})
    random.Random(5012).shuffle(plan)
    # Expected long-running cases go last; retain full six-hour thresholds and repetitions.
    plan.sort(key=lambda x:bool(x['dataset']=='TAS' and x['argument']=='5' or x['dataset']=='POW-L-approx' and x['family']=='core' and x['argument']=='2'))
    signatures={str(p.relative_to(ROOT)):digest(p) for p in [ROOT/'build/drivers/sigmod',ROOT/'build/drivers/vldb',ROOT/'build/extended/sigmod_extended']}
    metadata={'created_at_utc':now(),'phase':args.phase,'datasets':data,'plan':plan,'binary_sha256':signatures,'timeout_s':args.timeout,'memory_gib':args.memory_gib,'seed':5012,'source_sha256':digest(Path(__file__))}
    existing=out/'metadata.json'
    if existing.exists():
        old=json.loads(existing.read_text())
        if any(old[k]!=metadata[k] for k in ['datasets','plan','binary_sha256','timeout_s','memory_gib','source_sha256']):raise RuntimeError('Resume configuration changed; use a new run ID')
    else:save(existing,metadata)
    def terminate(signum,frame):raise InterruptedError('Signal '+str(signum))
    signal.signal(signal.SIGTERM,terminate)
    suite=Suite(out,args.timeout,args.memory_gib)
    try:
        for item in plan:suite.series(item,data[item['dataset']])
        rows=[json.loads(p.read_text()) for p in out.glob('*.json') if p.name not in ['metadata.json','running.json','summary.json']]
        trials=[r for r in rows if r.get('repeat',0)>0]
        summary={'completed_at_utc':now(),'series':len(plan),'attempt_records':len(rows),'successful_records':sum(r['status']=='ok' for r in rows),'trial_records':len(trials),'trial_status_counts':{s:sum(r['status']==s for r in trials) for s in sorted({r['status'] for r in trials})},'timeouts':sum(r['status']=='timeout' for r in rows),'memory_limit_records':sum(r['status']=='memory_limit' for r in rows),'other_failures':[r['label'] for r in rows if r['status'] not in ['ok','timeout','memory_limit']],'note':'Failed validation may also represent the first failed trial, explicitly linked by reused_attempt.'}
        save(out/'summary.json',summary);save(out/'running.json',{'status':'complete','updated_at':now()});print(json.dumps(summary))
    except BaseException as error:
        save(out/'running.json',{'status':'interrupted_or_error','error':repr(error),'updated_at':now()});raise

if __name__=='__main__':main()
