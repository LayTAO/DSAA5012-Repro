#!/usr/bin/env python3
"""Original integrity audit plus explicit cross-policy comparison exclusions."""
import json
import audit_supplement as base
from benchmark import ROOT,digest
from supplement_load_policy import POLICY

original_summary=base.summarize
def policy_summary(rows):
    result=original_summary(rows)
    policies=sorted({r.get('load_policy_id','load-policy-v1') for r in rows})
    result['load_policy_ids']=policies;result['mixed_load_policies']=len(policies)>1
    result['descriptive_means_only']=len(policies)>1
    if len(policies)>1:result['load_control_pass']=False
    return result

def main():
    base.summarize=policy_summary
    base.main()
    out=base.OUT;folder=out/'experiments';p=out/'audit.json';audit=json.loads(p.read_text())
    meta=json.loads((folder/'metadata-v2.json').read_text());handoff=json.loads((out/'policy-v2-handoff/receipt.json').read_text())
    checks=audit['checks']
    for name,sha in handoff['completed_record_sha256'].items():checks.append({'kind':'unchanged_v1_record','path':name,'match':digest(folder/name)==sha})
    for item in meta['pending_plan']:
        row=json.loads((folder/(item['label']+'.json')).read_text())
        checks.append({'kind':'v2_policy','label':item['label'],'match':row.get('load_policy_id')==POLICY['id'] and row.get('load_policy_sha256')==meta['policy_sha256'] and row.get('runner_source_sha256')==meta['source_sha256']})
    for name,sha in [('scripts/run_supplement_v2.py',meta['source_sha256']),('scripts/supplement_load_policy.py',meta['policy_module_sha256']),('configs/supplement-load-policy-v2.json',meta['policy_sha256'])]:
        checks.append({'kind':'v2_source','path':name,'match':digest(ROOT/name)==sha})
    for row in audit['filter_timer_calibration']:
        a=audit['groups'].get('|'.join(['timer',row['dataset'],'plain','0']),{})
        b=audit['groups'].get('|'.join(['timer',row['dataset'],row['variant'],'0']),{})
        if a.get('mixed_load_policies') or b.get('mixed_load_policies') or a.get('load_policy_ids')!=b.get('load_policy_ids'):
            row['candidate_for_filter_share']=False
            row['reasons'].append('Different resource-policy cohorts; means descriptive only, not an eligible calibrated comparison')
    audit['methodology_amendment']={'policy':POLICY,'new_attempts':len(meta['pending_plan']),'unchanged_old_attempts':len(handoff['completed_record_sha256']),'no_extra_attempts':True}
    audit['all_checks_pass']=all(x['match'] for x in checks)
    tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(audit,indent=2)+'\n');tmp.replace(p)
    if not audit['all_checks_pass']:raise RuntimeError('Policy-aware integrity audit failed')
if __name__=='__main__':main()
