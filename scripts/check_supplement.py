#!/usr/bin/env python3
"""Validate changed instrumentation on diverse small graphs before formal runs."""
import os,json,random,subprocess
from pathlib import Path
from benchmark import ROOT,digest
if os.environ.get('TMPDIR')!=str(ROOT/'.runtime/tmp'):raise RuntimeError('Guard required')
out=ROOT/'results/supplement-20261110/small-checks';out.mkdir(parents=True,exist_ok=True)
rng=random.Random(5012);cases=[[[1,2,3],[2,3,4],[4,5]],[[1,2],[2,3],[3,1]],[[1,2,3,4],[1,2,3,4],[4,5]],[[1,2],[4,5],[5,6]]]
for n in [5,9,13]:
 for j in range(4):cases.append([sorted(rng.sample(range(1,n+1),rng.randint(2,min(6,n)))) for k in range(2*n)])
results=[]
for i,edges in enumerate(cases):
 inp=out/f'case-{i}.hyp';inp.write_text(''.join(','.join(map(str,e))+'\n' for e in edges));hashes={}
 for variant in ['plain','chrono','tsc_full','tsc_sample32']:
  csv=out/f'{i}-{variant}.cores.csv'
  if variant=='plain':cmd=[str(ROOT/'build/drivers/sigmod'),str(inp),'0',str(csv)]
  else:cmd=[str(ROOT/('build/extended/sigmod_extended' if variant=='chrono' else 'build/supplement-20261110/sigmod_tsc')),str(inp),'stats','0','3000',str(csv)]
  env=dict(os.environ,REPRO_TIMER_STRIDE='32' if variant=='tsc_sample32' else '1',REPRO_TIMER_SEED='5012')
  p=subprocess.run(['taskset','-c','0',*cmd],capture_output=True,text=True,env=env,check=True,timeout=120)
  (out/f'{i}-{variant}.log').write_text(p.stdout+p.stderr);hashes[variant]=digest(csv)
  if variant.startswith('tsc'):
   q=json.loads(next(x.split(' ',1)[1] for x in p.stdout.splitlines() if x.startswith('SUPPLEMENT_TIMER ')))
   assert q['migrations']==0 and q['frequency_relative_spread']<=.005
 assert len(set(hashes.values()))==1,hashes
 results.append({'case':i,'edges':edges,'core_sha256':hashes})
(out/'summary.json').write_text(json.dumps({'cases':len(results),'variants':4,'all_complete_outputs_match':True,'cases_details':results},indent=2)+'\n')
print('Passed',len(results),'graphs across four variants.')
