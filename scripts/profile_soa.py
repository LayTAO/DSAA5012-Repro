#!/usr/bin/env python3
from pathlib import Path
import os,json,subprocess
from benchmark import ROOT,digest
if os.environ.get('TMPDIR')!=str(ROOT/'.runtime/tmp'):raise RuntimeError('Guard required')
metadata=json.loads((ROOT/'data/processed/scales-SOA/manifest.json').read_text())
expected=json.loads((ROOT/'configs/supplement-scale-expected.json').read_text())
rows=[]
for fraction,q in metadata['fractions'].items():
 p=ROOT/q['path'];sha=digest(p);key='SOA-E'+fraction.replace('.','p')
 if sha!=expected[key]['processed']['sha256']:raise RuntimeError('Historical scale SHA mismatch '+key)
 proc=subprocess.run(['taskset','-c','0',str(ROOT/'build/supplement-20261110/profile_initialization'),str(p)],capture_output=True,text=True,check=True)
 line=next(x.split(' ',1)[1] for x in proc.stdout.splitlines() if x.startswith('INIT_WORK '))
 rows.append(dict(dataset=key,fraction=float(fraction),input_sha256=sha,**json.loads(line)))
out=ROOT/'results/supplement-20261110/soa-initialization-work.json';out.write_text(json.dumps({'method':'Exact operation opportunities counted from input incidence; not elapsed timings. Existing historical phase timings remain separate.','rows':rows},indent=2)+'\n');print(out)
