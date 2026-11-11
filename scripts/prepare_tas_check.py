#!/usr/bin/env python3
"""Separate canonical-set TAS candidate; never overwrite historical ordered input."""
from pathlib import Path
import os,json,subprocess
from benchmark import ROOT,digest,input_stats
from prepare_cornell import canonicalize,unique_stats_and_vertices
from prepare_full_inputs import organize
if os.environ.get('TMPDIR')!=str(ROOT/'.runtime/tmp'):raise RuntimeError('Guard required')
source=ROOT/'data/processed/extended-TAS';out=ROOT/'data/processed/supplement-TAS-canonical';out.mkdir(parents=True,exist_ok=True)
if (out/'manifest.json').exists():print('Existing canonical TAS check retained');raise SystemExit(0)
records=out/'timestamped-canonical.hyp';unique=out/'unique-canonical.hyp'
if records.exists() or unique.exists():raise RuntimeError('Partial canonical candidate exists; inspect before retry')
temporal=canonicalize(source/'nverts.txt',source/'simplices.txt',records,ordered=False)
subprocess.run(['sort','--parallel=2','-S','512M','-T',os.environ['TMPDIR'],'-u',str(records),'-o',str(unique)],env=dict(os.environ,LC_ALL='C'),check=True)
stats,_=unique_stats_and_vertices(unique);processed=organize(unique,out);actual=input_stats(processed,allow_sparse=True)
old=json.loads((source/'manifest.json').read_text())
r={'dataset':'TAS-canonical-candidate','source_archive_sha256':old['source']['sha256'],'temporal':temporal,'unique':stats,'processed':actual,'preprocessing':'Sort and deduplicate member sets before external whole-edge deduplication; then author org and sortEV. Independent report scripts/hash not supplied, so count agreement alone is not input identity.','historical_ordered_processed':old['processed'],'independent_report_edge_count':5517054,'edge_count_matches_independent_report':actual['edges']==5517054}
(out/'manifest.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)
