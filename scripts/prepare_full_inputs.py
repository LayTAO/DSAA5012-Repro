#!/usr/bin/env python3
"""Checkpointed synthetic generation and edge-sampling preparation on guarded storage."""
import argparse
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
from benchmark import ROOT,digest


def audit(path):
    result=json.loads(subprocess.check_output([str(ROOT/'build/extended/audit_hypergraph'),str(path)],text=True))
    result.update(sha256=digest(path),bytes=path.stat().st_size)
    return result


def run(command,log):
    def limit():
        cap=500*1024**3;resource.setrlimit(resource.RLIMIT_AS,(cap,cap))
    with log.open('w') as output:
        subprocess.run(['/usr/bin/time','-v','-o',str(log.with_suffix('.time.txt')),*command],stdout=output,stderr=subprocess.STDOUT,check=True,preexec_fn=limit)


def organize(raw,out):
    working=out/'author-input.hyp';processed=Path(str(working)+'_sorted_by_edge_desc_node_asc.txt')
    native=str(ROOT/'build/native/HypergraphKCore')
    if not (out/'org.complete').exists():
        shutil.copyfile(raw,working)
        run([native,str(working),'org'],out/'org.log')
        (out/'org.complete').write_text(digest(working)+'\n')
    if not (out/'sort.complete').exists():
        run([native,str(working),'sortEV','desc','asc'],out/'sort.log')
        (out/'sort.complete').write_text(digest(processed)+'\n')
    return processed


def synthetic(dataset):
    profile=json.loads((ROOT/'configs/synthetic-profile.json').read_text());spec=profile['datasets'][dataset]
    out=ROOT/'data/processed'/('synthetic-'+dataset);out.mkdir(parents=True,exist_ok=True)
    if (out/'manifest.json').exists():return
    if shutil.disk_usage(ROOT).free<spec['minimum_free_gib']*1024**3:raise RuntimeError('Insufficient project storage')
    raw=out/'generated-raw.hyp'
    command=[str(ROOT/'build/extended/generate_synthetic'),str(raw),str(spec['requested_nodes']),str(spec['requested_edges']),str(profile['seed'])]
    if not (out/'generation.complete').exists():
        if raw.exists():raise RuntimeError('Incomplete raw generation exists; inspect it before retrying')
        run(command,out/'generation.log')
        if not raw.exists() or not raw.stat().st_size:raise RuntimeError('Generator produced no data')
        (out/'generation.complete').write_text(digest(raw)+'\n')
    raw_stats=audit(raw)
    processed=organize(raw,out);measured=audit(processed)
    paper=next(x for x in json.loads((ROOT/'configs/paper-profile.json').read_text())['datasets'] if x['id']==spec['paper_id'])
    manifest={'dataset':dataset,'paper_id':spec['paper_id'],'claim':profile['claim'],'requested_parameters':spec,'seed':profile['seed'],'generator':profile['generator'],'generation_command':command,'raw':raw_stats,'processed':measured,'paper_table4':paper,'generator_binary_sha256':digest(ROOT/'build/extended/generate_synthetic'),'preprocessing':'Author org; author sortEV desc asc; seeded author generator copy.'}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(dataset,json.dumps(measured),flush=True)


def scales(dataset):
    registry=json.loads((ROOT/'configs/full-datasets.json').read_text());spec=registry[dataset]
    source=ROOT/'data/processed'/spec['directory']/'author-input.hyp_sorted_by_edge_desc_node_asc.txt'
    source_manifest=json.loads((source.parent/'manifest.json').read_text())
    if digest(source)!=source_manifest['processed']['sha256']:raise RuntimeError('Source input changed')
    out=ROOT/'data/processed'/('scales-'+dataset);out.mkdir(parents=True,exist_ok=True)
    full=out/'full.hyp'
    if not full.exists():os.link(source,full)
    if not (out/'sampling.complete').exists():
        run([str(ROOT/'build/extended/sample_sizes'),str(full),'5012'],out/'sampling.log')
        (out/'sampling.complete').write_text('seed=5012\n')
    manifest={'dataset':dataset,'seed':5012,'source_sha256':source_manifest['processed']['sha256'],'sampling':'Seeded copy of author vary_edges; nested shuffled prefixes; author EOF empty-record behavior retained.','fractions':{}}
    for fraction in ['0.2','0.4','0.6','0.8']:
        raw=Path(str(full)+'_E_'+fraction+'.txt');sub=out/fraction;sub.mkdir(exist_ok=True)
        processed=organize(raw,sub);stats=audit(processed)
        manifest['fractions'][fraction]={'path':str(processed.relative_to(ROOT)),'processed':stats}
    manifest['fractions']['1.0']={'path':str(source.relative_to(ROOT)),'processed':source_manifest['processed']}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Prepared scales',dataset,flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('kind',choices=['synthetic','scales']);parser.add_argument('datasets',nargs='+');args=parser.parse_args()
    if os.environ.get('TMPDIR')!=str(ROOT/'.runtime/tmp'):raise RuntimeError('Use run_on_server.sh')
    for dataset in args.datasets:
        (synthetic if args.kind=='synthetic' else scales)(dataset)

if __name__=='__main__':main()
