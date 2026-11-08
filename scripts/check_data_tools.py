#!/usr/bin/env python3
"""Check deterministic author generation/sampling and the streaming data auditor."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import subprocess
from benchmark import ROOT,digest,input_stats


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if os.environ.get('TMPDIR')!=str(ROOT/'.runtime/tmp'):raise RuntimeError('Use guarded environment')
    out=args.output.resolve()
    if not out.is_relative_to(ROOT/'results'):raise RuntimeError('Output must be in project results')
    out.mkdir(parents=True,exist_ok=False)
    checks=[]
    def run(command):
        result=subprocess.run(list(map(str,command)),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=120,check=True)
        with (out/'commands.log').open('a') as stream:stream.write(result.stdout+'\n')
        return result.stdout
    for name,seed in [('a',5012),('b',5012),('c',5013)]:
        run([ROOT/'build/extended/generate_synthetic',out/(name+'.hyp'),2000,1800,seed])
    assert digest(out/'a.hyp')==digest(out/'b.hyp')
    assert digest(out/'a.hyp')!=digest(out/'c.hyp')
    checks.append('Same seed reproduces bytes; a different seed changes the graph')
    normalized=out/'normalized.hyp'
    normalized.write_text('\n'.join(line.strip().rstrip(',') for line in (out/'a.hyp').read_text().splitlines())+'\n')
    expected=input_stats(normalized,allow_sparse=True)
    audited=json.loads(run([ROOT/'build/extended/audit_hypergraph',out/'a.hyp']))
    for key,value in audited.items():
        if key in expected:assert value==expected[key],(key,value,expected[key])
    checks.append('Streaming audit matches independent Python statistics, including trailing commas')
    for name in ['sample-a.hyp','sample-b.hyp']:
        shutil.copyfile(normalized,out/name)
        run([ROOT/'build/extended/sample_sizes',out/name,5012])
    previous=Counter()
    for fraction in ['0.2','0.4','0.6','0.8']:
        first=Path(str(out/'sample-a.hyp')+'_E_'+fraction+'.txt')
        second=Path(str(out/'sample-b.hyp')+'_E_'+fraction+'.txt')
        assert digest(first)==digest(second)
        current=Counter(line for line in first.read_text().splitlines() if line.strip())
        assert not previous-current,'Samples must be nested multisets'
        nominal=int((expected['edges']+1)*float(fraction))
        assert nominal-1<=sum(current.values())<=nominal
        previous=current
    checks.append('Seeded samples are byte-reproducible nested prefixes, with audited EOF behavior')
    invalid=out/'invalid.hyp';invalid.write_text('0,1\n')
    rejected=subprocess.run([str(ROOT/'build/extended/audit_hypergraph'),str(invalid)],capture_output=True,text=True)
    assert rejected.returncode!=0 and 'outside supported' in rejected.stderr
    checks.append('Auditor rejects zero-based inputs before benchmarking')
    summary={'checks':checks,'passed':len(checks),'generator_sha256':digest(ROOT/'build/extended/generate_synthetic'),
             'sampler_sha256':digest(ROOT/'build/extended/sample_sizes'),'auditor_sha256':digest(ROOT/'build/extended/audit_hypergraph')}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))

if __name__=='__main__':main()
