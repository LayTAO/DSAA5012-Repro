#!/usr/bin/env python3
"""Audit all supplemental attempts without dropping failed or slower repetitions."""
import collections,datetime,json,os,statistics
from pathlib import Path
from benchmark import ROOT,digest

OUT=ROOT/'results/supplement-20261110'

def summarize(rows):
    complete=len(rows)==3 and sorted(r['repeat'] for r in rows)==[1,2,3]
    success=complete and all(r['status']=='ok' and r.get('historical_core_match') for r in rows)
    clean=success and all(r['load_control_pass'] for r in rows)
    result={'attempts':len(rows),'statuses':dict(collections.Counter(r['status'] for r in rows)),
            'three_complete_correct_attempts':success,'load_control_pass':bool(clean),
            'records':[r['label'] for r in rows]}
    # Means are unavailable for any group containing a failure or a missing repeat.
    if success:
        for key in ['reported_init_s','reported_execution_s','reported_total_s','peak_rss_kib','D_over_CplusD']:
            if all(key in r for r in rows):
                values=[r[key] for r in rows]
                result[key]={'values':values,'mean':statistics.mean(values),'stdev':statistics.stdev(values)}
    return result

def main():
    if os.environ.get('TMPDIR')!=str(ROOT/'.runtime/tmp'):raise RuntimeError('Guard required')
    folder=OUT/'experiments';meta=json.loads((folder/'metadata.json').read_text())
    expected=json.loads((ROOT/'configs/supplement-expected.json').read_text())
    checks=[];rows=[];pending=[];groups=collections.defaultdict(list)
    for name,sha in meta['binary_sha256'].items():
        checks.append({'kind':'binary','path':name,'match':digest(ROOT/name)==sha})
    for item in meta['plan']:
        path=folder/(item['label']+'.json')
        if not path.exists():pending.append(item['label']);continue
        r=json.loads(path.read_text());rows.append(r)
        assert all(r[k]==v for k,v in item.items()),'Plan/record identity mismatch'
        assert r['timeout_s']==21600 and r['memory_limit_bytes']==500*1024**3
        assert r['input_sha256']==expected[r['dataset']]['manifest']['processed']['sha256']
        binary=next(p for p in r['command'] if p.startswith(str(ROOT/'build')))
        assert r['binary_sha256']==meta['binary_sha256'][str(Path(binary).relative_to(ROOT))]
        checks.append({'kind':'log','label':r['label'],'match':digest(folder/(r['label']+'.log'))==r['log_sha256']})
        if r['status']=='ok':
            actual=digest(folder/(r['label']+'.cores.csv'))
            checks.append({'kind':'complete_core','label':r['label'],'match':actual==r['core_sha256'] and actual in expected[r['dataset']]['core_sha256_values']})
        groups[(r['study'],r['dataset'],r['variant'],r['argument'])].append(r)
    summaries={'|'.join(k):summarize(v) for k,v in groups.items()}
    calibration=[]
    for dataset in dict.fromkeys(i['dataset'] for i in meta['plan'] if i['study']=='timer'):
        base=summaries.get('|'.join(['timer',dataset,'plain','0']),{})
        for variant in ['chrono','tsc_full','tsc_sample32']:
            key=('timer',dataset,variant,'0');group=summaries.get('|'.join(key),{})
            record={'dataset':dataset,'variant':variant,'candidate_for_filter_share':False,'reasons':[]}
            if not (base.get('three_complete_correct_attempts') and group.get('three_complete_correct_attempts')):
                record['reasons'].append('Incomplete, failed or incorrect three-attempt group')
            else:
                ratio=group['reported_execution_s']['mean']/base['reported_execution_s']['mean']
                record['instrumented_over_plain_execution']=ratio
                if not .90<=ratio<=1.10:record['reasons'].append('Execution perturbation exceeds predeclared +/-10% criterion')
                if not (base['load_control_pass'] and group['load_control_pass']):record['reasons'].append('Load control violation; all attempts retained')
                if variant=='chrono':record['reasons'].append('Historical chrono instrumentation is a diagnostic comparator, not newly calibrated')
                else:
                    attempts=groups[key]
                    if any(r['timer']['migrations'] or r['timer']['frequency_relative_spread']>.005 for r in attempts):record['reasons'].append('TSC calibration instability or CPU migration')
                    if any(r['timer'][region]['samples']<100 for r in attempts for region in ['C','D']):record['reasons'].append('Fewer than 100 samples for a measured region')
                    for mode in ['raw_estimate_s','empty_pair_adjusted_estimate_s']:
                        values=[]
                        for r in attempts:
                            c,d=(r['timer'][region][mode] for region in ['C','D'])
                            values.append(d/(c+d) if c>=0 and d>=0 and c+d>0 else None)
                        record[mode+'_D_over_CplusD']={'values':values,'mean':statistics.mean(values) if None not in values else None}
                    record['candidate_for_filter_share']=not record['reasons']
            calibration.append(record)
    output={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'planned_attempts':len(meta['plan']),'recorded_attempts':len(rows),'pending':pending,
            'statuses':dict(collections.Counter(r['status'] for r in rows)),
            'checks':checks,'all_checks_pass':all(c['match'] for c in checks),
            'groups':summaries,'filter_timer_calibration':calibration,
            'limitations':['Shared server: load monitoring is not exclusive hardware reservation.',
                          'TSC durations include scheduling stalls; empty-pair subtraction cannot remove all measurement perturbation.',
                          'Eligibility is a diagnostic acceptance criterion, not proof of unbiased timing.',
                          'Canonical TAS count agreement does not establish identical independent input without its script/hash.']}
    for name,path in [('tas','data/processed/supplement-TAS-canonical/manifest.json'),('soa','results/supplement-20261110/soa-initialization-work.json')]:
        if (ROOT/path).exists():output[name]=json.loads((ROOT/path).read_text())
    target=OUT/'audit.json';tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(output,indent=2)+'\n');tmp.replace(target)
    print(json.dumps({k:output[k] for k in ['planned_attempts','recorded_attempts','statuses','all_checks_pass']}))
    if pending or not output['all_checks_pass']:raise RuntimeError('Audit incomplete or integrity mismatch; see audit.json')
if __name__=='__main__':main()
