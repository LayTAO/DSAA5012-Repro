#!/usr/bin/env python3
"""Audit full-paper coverage and compare complete, validated groups with paper values."""
import argparse
from collections import Counter,defaultdict
import datetime
import json
from pathlib import Path
import statistics

METRICS=['reported_init_s','reported_execution_s','reported_total_s','peak_rss_kib','total_before_export_wall_s','ruc_fraction_of_execution']
SUITES=['full-real-001','full-synthetic-small001','full-synthetic-large001']

def read(path):return json.loads(path.read_text())

def summarize(root):
    registry=read(root/'configs/full-datasets.json');groups=defaultdict(list);expected={};datasets={};validation={};references={};suite_states={}
    for dataset,spec in registry.items():
        manifest=read(root/'data/processed'/spec['directory']/'manifest.json')
        datasets[dataset]={'paper_id':spec['paper_id'],'manifest':manifest,'alignment_note':spec['alignment_note']}
        if spec.get('existing_result'):
            out=root/'results'/spec['existing_result'];summary=read(out/'summary.json')
            if summary['data']['sha256']!=manifest['processed']['sha256']:raise RuntimeError('Old input mismatch: '+dataset)
            references[dataset]=summary['core_sha256']
            for row in read(out/'validation.json'):
                argument='OPTIV' if row['method']=='vldb_OPTIV' else row['method'].split('_')[-1]
                validation[(dataset,'core',argument)]=row
            for row in map(json.loads,(out/'runs.jsonl').read_text().splitlines()):
                argument='OPTIV' if row['method']=='vldb_OPTIV' else row['method'].split('_')[-1]
                key=(dataset,'core',argument);expected[key]=3
                row=dict(row,dataset=dataset,paper_id=spec['paper_id'],argument=argument,repeat=row['repeat'],source=str(out.relative_to(root)))
                groups[key].append(row)
    for dataset in ['POW-S-approx','POW-L-approx']:
        path=root/'data/processed'/('synthetic-'+dataset)/'manifest.json'
        if path.exists():datasets[dataset]={'paper_id':dataset.replace('-approx',''),'manifest':read(path),'alignment_note':'Same-scale synthetic approximation, not the original paper input.'}
    # Define the complete target even before a later suite has started.
    for dataset,spec in registry.items():
        if not spec.get('existing_result'):
            for a in ['0','1','2','3','4','5','OPTIV']:expected[(dataset,'core',a)]=3
        expected[(dataset,'stats','0')]=3
        if dataset in ['DF','THS','TAS','AMZ']:
            for a in ['1','2','5']:expected[(dataset,'stats',a)]=1
        if dataset in ['AMZ','SOA']:
            for a in [1,2,4,8,16,32,64]:expected[(dataset,'parallel',str(a))]=3
        if dataset in ['AMZ','TAS','SOA','AM']:
            for f in ['0p2','0p4','0p6','0p8','1p0']:expected[(dataset+'-E'+f,'scale','0')]=3
    for dataset in ['POW-S-approx','POW-L-approx']:
        for a in ['0','1','2','OPTIV']:expected[(dataset,'core',a)]=3
        expected[(dataset,'stats','0')]=3
        if dataset=='POW-L-approx':
            for a in [1,2,4,8,16,32,64]:expected[(dataset,'parallel',str(a))]=3
    for name in SUITES:
        out=root/'results'/name
        if not (out/'metadata.json').exists():suite_states[name]={'status':'not_started'};continue
        metadata=read(out/'metadata.json');suite_states[name]=read(out/'running.json') if (out/'running.json').exists() else {'status':'unknown'}
        for dataset,spec in metadata['datasets'].items():
            if dataset in datasets and spec['processed']['sha256']!=datasets[dataset]['manifest']['processed']['sha256']:raise RuntimeError('Suite input mismatch: '+dataset)
        for path in out.glob('reference-*.json'):
            row=read(path)
            if row['status']=='ok':references[row['dataset']]=row['core_sha256']
        for path in sorted(out.glob('*.json')):
            row=read(path)
            if 'label' not in row or 'repeat' not in row or row['label'].startswith('reference-'):continue
            family=row['label'].split('-')[0];key=(row['dataset'],family,str(row['argument']))
            if key not in expected:raise RuntimeError('Unexpected trial group: '+str(key))
            if row['input_sha256']!=metadata['datasets'][row['dataset']]['processed']['sha256']:raise RuntimeError('Trial input mismatch')
            binary=row['command'][row['command'].index('taskset')+3]
            binary_path='build/'+binary.split('/build/',1)[1]
            if row['binary_sha256']!=metadata['binary_sha256'][binary_path]:raise RuntimeError('Trial binary changed')
            if row['repeat']==0:validation[key]=row
            else:groups[key].append(dict(row,source=str(path.relative_to(root))))
    aggregated=[];raw_status=Counter()
    for key,repetitions in expected.items():
        dataset,family,argument=key;rows=groups[key]
        repeats=[r['repeat'] for r in rows]
        if len(repeats)!=len(set(repeats)) or any(r<1 or r>repetitions for r in repeats):raise RuntimeError('Duplicate or unexpected repeat: '+str(key))
        raw_status.update(r['status'] for r in rows)
        successes=[r for r in rows if r['status']=='ok']
        core_checks=[r for r in rows if r['status']=='ok' and r.get('exported_cores')]
        if key in validation and validation[key]['status']=='ok':core_checks.append(validation[key])
        correct=bool(core_checks) and dataset in references and all(r.get('core_sha256')==references[dataset] for r in core_checks)
        if family=='parallel':correct=correct and len(core_checks)==len(successes)
        complete=len(rows)==repetitions
        status='complete' if complete and len(successes)==repetitions and correct else ('unvalidated' if complete and len(successes)==repetitions else ('completed_with_failures' if complete else 'pending'))
        item={'dataset':dataset,'paper_id':dataset.split('-E')[0].replace('-approx',''),'family':family,'argument':argument,
              'expected_trials':repetitions,'recorded_trials':len(rows),'successful_trials':len(successes),'status':status,
              'full_core_outputs_match':correct,'trial_status_counts':dict(Counter(r['status'] for r in rows)),'trial_sources':[r['source'] for r in rows]}
        if status=='complete':
            for metric in METRICS:
                values=[r[metric] for r in successes if metric in r]
                if len(values)==repetitions:item[metric]={'mean':statistics.mean(values),'min':min(values),'max':max(values),'n':len(values)}
            if family=='stats':
                traces=[r.get('iteration_trace',[]) for r in successes]
                item['iteration_trace']=traces[0];item['identical_iteration_traces']=all(t==traces[0] for t in traces)
                computed=sum(t['computed'] for t in traces[0]);changed=sum(t['changed'] for t in traces[0])
                item['updated_per_computed']=changed/computed if computed else None
        aggregated.append(item)
    index={(r['dataset'],r['family'],r['argument']):r for r in aggregated};comparisons=[]
    paper=read(root/'configs/paper-digitized.json')
    for panel in paper['panels']:
        metric={4:'reported_total_s',5:'reported_execution_s',6:'peak_rss_kib',8:'reported_execution_s'}[panel['figure']]
        for value in panel['values']:
            dataset=value['dataset']+('-approx' if value['dataset'].startswith('POW-') else '')
            argument='OPTIV' if value['method']=='vldb_OPTIV' else value['method'].split('_')[-1]
            actual=index.get((dataset,'core',argument));measured=None
            if actual and actual['status']=='complete':measured=actual[metric]['mean']/(1024 if panel['figure']==6 else 1)
            comparisons.append({'figure':panel['figure'],'dataset':dataset,'argument':argument,'paper_status':value['status'],'paper_estimate':value['estimate'],
                'measured_mean':measured,'measured_status':actual['status'] if actual else 'not_in_plan',
                'measured_over_paper':measured/value['estimate'] if measured is not None and value['estimate'] else None,
                'memory_unit_note':'Measured MiB; paper axis MB base unspecified' if panel['figure']==6 else None})
    total=sum(expected.values());recorded=sum(len(rows) for rows in groups.values())
    workflow=root/'results/full-workflow-001/status.json'
    return {'generated_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'coverage':{'expected_trial_records':total,'recorded_trial_records':recorded,'pending_trial_records':total-recorded,
            'status_counts':dict(raw_status),'complete_validated_groups':sum(r['status']=='complete' for r in aggregated),'expected_groups':len(expected),
            'all_trials_recorded':recorded==total,'all_groups_successful_and_validated':all(r['status']=='complete' for r in aggregated)},
        'workflow':read(workflow) if workflow.exists() else {'status':'unknown'},'suites':suite_states,'datasets':datasets,'groups':aggregated,'paper_comparisons':comparisons,
        'failure_evidence':read(root/'results/failure-evidence.json') if (root/'results/failure-evidence.json').exists() else {'records':[]},
        'interpretation':['Only complete groups with matching full core outputs have published means. No successful-only means are reported for failed groups.',
            'Twelve nonzero-method iteration traces have one deterministic observation; all other groups have three trials.',
            'Paper estimates and text labels are separate from measurements. Hardware and publicly available inputs differ.',
            'RLIMIT_AS limits virtual address space, not RSS or the paper hardware RAM. A memory_limit result is not proof of identical paper OOM.',
            'Parallel outputs are validated for every repeat. Instrumented statistics are not used as core-performance timing measurements.']}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('input',type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=summarize(args.input);args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result['coverage']))

if __name__=='__main__':main()
