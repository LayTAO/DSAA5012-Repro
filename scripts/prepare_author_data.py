#!/usr/bin/env python3
"""Audit the original VLDB authors' public data archive against SIGMOD Table 4."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile
from benchmark import ROOT, digest, input_stats

MEMBERS = {'CO':'congress-bills.hyp','DB':'DBLP.hyp','AM':'aminer.hyp'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('dataset',choices=MEMBERS)
    args=parser.parse_args()
    if os.environ.get('TMPDIR') != str(ROOT/'.runtime/tmp'):
        raise RuntimeError('Run through scripts/run_on_server.sh')
    archive=ROOT/'data/raw/vldb-author/datasets.archive'
    raw=archive.parent/MEMBERS[args.dataset]
    member='data/datasets/real/'+MEMBERS[args.dataset]
    with zipfile.ZipFile(archive) as compressed:
        if not raw.exists():
            with compressed.open(member) as source,raw.open('wb') as target:
                shutil.copyfileobj(source,target)
    directory=ROOT/'data/processed'/('author-'+args.dataset)
    if (directory/'manifest.json').exists():
        print((directory/'manifest.json').read_text())
        return
    directory.mkdir(exist_ok=True)
    # Exact raw file layout, without changing duplicate-edge policy or numbering.
    stats=input_stats(raw,allow_sparse=True)
    profile=json.loads((ROOT/'configs/paper-profile.json').read_text())
    reported=next(row for row in profile['datasets'] if row['id']==args.dataset)
    array_nodes=stats['max_vertex_id']+1
    with raw.open('rb') as stream:
        stream.seek(-1,2)
        trailing_newline=stream.read(1)==b'\n'
    array_edges=stats['edges']+1+int(trailing_newline)
    match={'true_counts_match':stats['vertices']==reported['reported_n'] and stats['edges']==reported['reported_m'],
           'upstream_array_counts_match':array_nodes==reported['reported_n'] and array_edges==reported['reported_m']}
    working=directory/'author-input.hyp'
    shutil.copyfile(raw,working)
    binary=ROOT/'build/native/HypergraphKCore'
    commands=[[str(binary),str(working),'org'],[str(binary),str(working),'sortEV','desc','asc']]
    with (directory/'preprocessing.log').open('w') as log:
        for command in commands:
            subprocess.run(command,check=True,stdout=log,stderr=subprocess.STDOUT,timeout=3600)
    processed=Path(str(working)+'_sorted_by_edge_desc_node_asc.txt')
    manifest={'candidate_paper_id':args.dataset,
              'source':{'page':'https://github.com/toggled/vldbsubmission/tree/ea540958c176058b44830960753d854017719be2',
                        'archive_url':'https://drive.google.com/file/d/12cvz-XtfQUbmj-gqlT9z4DKGMuhqLGjs/view',
                        'member':member},'archive_sha256':digest(archive),'raw':stats,
              'raw_upstream_array_nodes':array_nodes,'raw_upstream_array_edges':array_edges,
              'paper_table4':reported,'paper_count_match':match,'commands':commands,
              'preprocessing':'Preserve provided hyperedges; author org and sortEV desc asc; preserve ID gaps',
              'processed':input_stats(processed,allow_sparse=True)}
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2),flush=True)


if __name__=='__main__':
    main()
