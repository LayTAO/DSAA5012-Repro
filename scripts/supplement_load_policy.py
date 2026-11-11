"""Versioned, CPU-local resource gate; no retrospectively relaxed old records."""
import json,os,re,time
from pathlib import Path
from benchmark import ROOT

POLICY_PATH=ROOT/'configs/supplement-load-policy-v2.json'
POLICY=json.loads(POLICY_PATH.read_text())

def expand_list(text):
    values=[]
    for group in text.strip().split(','):
        if '-' in group:
            a,b=map(int,group.split('-'));values.extend(range(a,b+1))
        else:values.append(int(group))
    return values

def node_cpus():
    return expand_list(Path('/sys/devices/system/node/node0/cpulist').read_text())

def busy(a,b,key):
    total=b['cpu'][key]['total']-a['cpu'][key]['total']
    idle=b['cpu'][key]['idle']-a['cpu'][key]['idle']
    return 100*(1-idle/total) if total>0 else 0

def node_busy(a,b):
    total=sum(b['cpu'][k]['total']-a['cpu'][k]['total'] for k in a['cpu'])
    idle=sum(b['cpu'][k]['idle']-a['cpu'][k]['idle'] for k in a['cpu'])
    return 100*(1-idle/total) if total>0 else 0

def pressure(name,kind):
    for line in (Path('/proc/pressure')/name).read_text().splitlines():
        fields=line.split()
        if fields[0]==kind:return float(dict(x.split('=') for x in fields[1:])['avg10'])
    raise RuntimeError('Missing pressure metric '+name+'/'+kind)

def algorithm_task(pid):
    # Follow only this attempt's direct child chain, never unrelated processes.
    for _ in range(5):
        try:
            folder=Path('/proc')/str(pid)
            cmd=(folder/'cmdline').read_bytes().split(b'\0')[0].decode()
            if cmd.startswith(str(ROOT/'build')+'/'):
                raw=(folder/'stat').read_text();s=raw[raw.rfind(')')+2:].split()
                return {'pid':pid,'start_ticks':int(s[19]),'cpu_ticks':int(s[11])+int(s[12])}
            children=(folder/'task'/str(pid)/'children').read_text().split()
            if len(children)!=1:return None
            pid=int(children[0])
        except (OSError,ValueError,IndexError):return None
    return None

def snapshot(pid=None):
    wanted={'cpu'+str(n) for n in node_cpus()};cpu={}
    for line in Path('/proc/stat').read_text().splitlines():
        z=line.split()
        if z and z[0] in wanted:
            values=list(map(int,z[1:9]));cpu[z[0]]={'total':sum(values),'idle':values[3]+values[4]}
    return {'monotonic_s':time.monotonic(),'cpu':cpu,'load':os.getloadavg(),
            'memavailable_kib':int(re.search(r'MemAvailable:\s+(\d+)',Path('/proc/meminfo').read_text()).group(1)),
            'cpu_pressure_some_avg10_pct':pressure('cpu','some'),
            'memory_pressure_some_avg10_pct':pressure('memory','some'),
            'io_pressure_full_avg10_pct':pressure('io','full'),
            'algorithm_task':algorithm_task(pid) if pid else None}

def system_reasons(x,before=False):
    p=POLICY;reasons=[]
    if x['load'][0]>p['max_load1']:reasons.append('global_load')
    for key in ['cpu_pressure_some_avg10_pct','memory_pressure_some_avg10_pct','io_pressure_full_avg10_pct']:
        if x[key]>p['max_'+key]:reasons.append(key)
    cap=p['min_memory_available_before_gib' if before else 'min_memory_available_during_gib']
    if x['memavailable_kib']<=cap*1024**2:reasons.append('available_memory')
    return reasons

def gate_decision(a,b):
    p=POLICY;reasons=system_reasons(b,before=True)
    metrics={'cpu0_busy_pct':busy(a,b,'cpu0'),'cpu64_busy_pct':busy(a,b,'cpu64'),'node0_busy_pct':node_busy(a,b)}
    if metrics['cpu0_busy_pct']>p['max_cpu_busy_before_pct']:reasons.append('cpu0_busy')
    if metrics['cpu64_busy_pct']>p['max_sibling_busy_pct']:reasons.append('sibling_busy')
    if metrics['node0_busy_pct']>p['max_node_busy_before_pct']:reasons.append('numa_node_busy')
    return dict(metrics,accepted=not reasons,reasons=reasons)

def assess(before,monitor,elapsed):
    p=POLICY;reasons=set();sibling=[];node=[];other=[];coverage=0
    for x in monitor:reasons.update(system_reasons(x))
    for a,b in zip([before,*monitor],monitor):
        dt=b['monotonic_s']-a['monotonic_s']
        # A one-tick change across a sub-millisecond boundary is not 100% busy
        # over a meaningful observation interval. Keep raw samples regardless.
        if dt<p['minimum_cpu_interval_seconds']:continue
        sibling.append(busy(a,b,'cpu64'));node.append(node_busy(a,b))
        x,y=a.get('algorithm_task'),b.get('algorithm_task')
        if x and y and (x['pid'],x['start_ticks'])==(y['pid'],y['start_ticks']):
            own=(y['cpu_ticks']-x['cpu_ticks'])/os.sysconf('SC_CLK_TCK')/dt*100
            other.append(max(0,busy(a,b,'cpu0')-own));coverage+=dt
    coverage_fraction=min(1,coverage/elapsed) if elapsed else 0
    if not sibling or max(sibling)>p['max_sibling_busy_pct']:reasons.add('sibling_busy_or_unobserved')
    if not node or max(node)>p['max_node_busy_during_pct']:reasons.add('numa_node_busy_or_unobserved')
    if coverage_fraction<p['min_cpu0_observation_fraction']:reasons.add('cpu0_observation_incomplete')
    if other and max(other)>p['max_other_cpu0_busy_during_pct']:reasons.add('other_cpu0_activity')
    return {'load_control_pass':not reasons,'load_control_reasons':sorted(reasons),
            'load_max':max(x['load'][0] for x in monitor),
            'sibling_busy_max_pct':max(sibling,default=None),'node0_busy_max_pct':max(node,default=None),
            'other_cpu0_busy_max_pct':max(other,default=None),'cpu0_observation_fraction':coverage_fraction}
