#!/usr/bin/env python3
"""Audit official extended data and apply the published org/sortEV pipeline."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import zipfile
from benchmark import ROOT,digest,input_stats
from prepare_cornell import canonicalize,unique_stats_and_vertices

def prepare(name):
    spec=json.loads((ROOT/'configs/extended-datasets.json').read_text())[name]
    archive=ROOT/'data/raw/cornell'/(spec['name']+'.'+spec['format'])
    receipt=json.loads(archive.with_name(archive.name+'.download.json').read_text())
    if digest(archive)!=receipt['sha256']:raise RuntimeError('Raw archive checksum changed')
    out=ROOT/'data/processed'/('extended-'+name)
    if (out/'manifest.json').exists():
        print('Reusing',name,flush=True);return
    out.mkdir(parents=True,exist_ok=True)
    working=out/'author-input.hyp'
    details={}
    if spec['format']=='tar.gz':
        members={}
        with tarfile.open(archive,'r:gz') as tar:
            for member in tar:
                for kind in ['nverts','simplices']:
                    if member.isfile() and member.name.endswith('-'+kind+'.txt'):
                        if kind in members:raise RuntimeError('Ambiguous tar member')
                        target=out/(kind+'.txt')
                        with tar.extractfile(member) as source,target.open('wb') as output:shutil.copyfileobj(source,output)
                        members[kind]=target
        if set(members)!={'nverts','simplices'}:raise RuntimeError('Missing temporal arrays')
        records=out/'timestamped-ordered.hyp'
        details['temporal']=canonicalize(members['nverts'],members['simplices'],records,ordered=True)
        raw=out/'unique-ordered.hyp'
        subprocess.run(['sort','--parallel=2','-S','512M','-T',os.environ['TMPDIR'],'-u',str(records),'-o',str(raw)],env=dict(os.environ,LC_ALL='C'),check=True)
        details['unique'],_=unique_stats_and_vertices(raw)
        policy='Deduplicate original ordered simplex lists, then author org and sortEV desc asc'
    else:
        raw=out/'raw-hyperedges.hyp';member=spec['name']+'/hyperedges-'+spec['name']+'.txt'
        with zipfile.ZipFile(archive) as z,z.open(member) as source,raw.open('wb') as output:shutil.copyfileobj(source,output)
        details['zip_member']=member
        policy='Preserve original hyperedge records, then author org and sortEV desc asc'
    print('Auditing',name,flush=True)
    raw_stats=input_stats(raw,allow_sparse=True)
    shutil.copyfile(raw,working)
    binary=ROOT/'build/native/HypergraphKCore'
    commands=[[str(binary),str(working),'org'],[str(binary),str(working),'sortEV','desc','asc']]
    with (out/'preprocess.log').open('w') as log:
        for command in commands:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=21600)
    processed=Path(str(working)+'_sorted_by_edge_desc_node_asc.txt')
    measured=input_stats(processed,allow_sparse=True)
    paper=next(x for x in json.loads((ROOT/'configs/paper-profile.json').read_text())['datasets'] if x['id']==name)
    checks={'raw_true_counts':raw_stats['vertices']==paper['reported_n'] and raw_stats['edges']==paper['reported_m'],
            'raw_array_counts':raw_stats['max_vertex_id']+1==paper['reported_n'] and raw_stats['edges']+2==paper['reported_m'],
            'processed_array_counts':measured['max_vertex_id']+1==paper['reported_n'] and measured['edges']+2==paper['reported_m'],
            'processed_edges_array_match':measured['edges']+2==paper['reported_m']}
    result=dict(dataset=name,source=receipt,raw=raw_stats,processed=measured,details=details,preprocessing=policy,commands=commands,paper_table4=paper,paper_count_match=checks)
    (out/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(name,json.dumps({'processed':measured,'alignment':checks}),flush=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('datasets',nargs='+',choices=['THS','TAS','SOA','AMZ']);args=parser.parse_args()
    if os.environ.get('TMPDIR')!=str(ROOT/'.runtime/tmp'):raise RuntimeError('Use run_on_server.sh')
    if shutil.disk_usage(ROOT).free<50*1024**3:raise RuntimeError('At least 50 GiB free storage required')
    for name in args.datasets:prepare(name)

if __name__=='__main__':main()
