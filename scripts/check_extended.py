#!/usr/bin/env python3
"""Check instrumented and parallel upstream implementations before large experiments."""
import argparse
import csv
import json
import os
import random
import subprocess
import sys
from pathlib import Path
from benchmark import ROOT,digest
sys.path.insert(0,str(ROOT/'src'))
from repro.oracle import core_numbers

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve()
    if not out.is_relative_to(ROOT/'results') or os.environ.get('TMPDIR')!=str(ROOT/'.runtime/tmp'):
        raise RuntimeError('Use guarded storage and an output below results/')
    out.mkdir(parents=True,exist_ok=False)
    rng=random.Random(5012)
    cases=[[[1],[2],[3]],[[3],[7,9],[3,9]],[[1,2],[1,2],[2,3]],[[1,2],[2,3],[3,4],[4,1],[1,3,5],[2,4,6]]]
    for _ in range(100):
        n=rng.randint(2,12)
        edges=[list(range(1,n+1))]
        edges.extend(rng.sample(range(1,n+1),rng.randint(1,n)) for _ in range(rng.randint(1,24)))
        cases.append(edges)
    modes=[('stats',i) for i in [0,1,2,3,4,5,6]]+[('parallel',t) for t in [1,2,4,8]]
    failures=[];unsupported=[];checks=0
    env=dict(os.environ,OMP_DYNAMIC='FALSE',OMP_PROC_BIND='TRUE')
    for index,edges in enumerate(cases):
        hyp=out/f'{index:03d}.hyp'
        hyp.write_text('\n'.join(','.join(map(str,sorted(set(e)))) for e in edges))
        expected=core_numbers(edges)
        for mode,argument in modes:
            checks+=1;stem=f'{index:03d}-{mode}-{argument}';core=out/(stem+'.csv')
            run=subprocess.run([str(ROOT/'build/extended/sigmod_extended'),str(hyp),mode,str(argument),'3000',str(core)],capture_output=True,text=True,timeout=60,env=env)
            (out/(stem+'.log')).write_text(run.stdout+run.stderr)
            if run.returncode and 'UPSTREAM_UNSUPPORTED:' in run.stderr:
                unsupported.append({'case':index,'mode':mode,'argument':argument});continue
            if run.returncode:
                failures.append({'case':index,'mode':mode,'argument':argument,'exit':run.returncode});continue
            with core.open() as stream:rows=list(csv.DictReader(stream))
            actual={int(r['vertex']):int(r['core']) for r in rows}
            if actual!=expected or len(rows)!=len(actual):
                failures.append({'case':index,'mode':mode,'argument':argument,'actual':actual,'expected':expected})
    result={'cases':len(cases),'attempted':checks,'passed':checks-len(failures)-len(unsupported),'unsupported':unsupported,'failures':failures,'binary_sha256':digest(ROOT/'build/extended/sigmod_extended'),'seed':5012}
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    return int(bool(failures))

if __name__=='__main__':raise SystemExit(main())
