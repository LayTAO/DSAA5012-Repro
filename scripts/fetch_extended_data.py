#!/usr/bin/env python3
"""Download only the four official extended inputs, directly on guarded server storage."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import urllib.request
import zipfile
from benchmark import ROOT, digest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('datasets',nargs='+',choices=['THS','TAS','SOA','AMZ'])
    args=parser.parse_args()
    if os.environ.get('TMPDIR')!=str(ROOT/'.runtime/tmp'):
        raise RuntimeError('Use run_on_server.sh')
    registry=json.loads((ROOT/'configs/extended-datasets.json').read_text())
    base=ROOT/'data/raw/cornell';base.mkdir(parents=True,exist_ok=True)
    for name in args.datasets:
        spec=registry[name];target=base/(spec['name']+'.'+spec['format'])
        receipt=target.with_name(target.name+'.download.json')
        if target.exists():
            if not receipt.exists() or json.loads(receipt.read_text())['sha256']!=digest(target):
                raise RuntimeError('Existing archive lacks a matching receipt: '+str(target))
            print('Verified existing',name,flush=True)
            continue
        if shutil.disk_usage(ROOT).free<30*1024**3:
            raise RuntimeError('Less than 30 GiB of free project storage')
        url='https://drive.usercontent.google.com/download?id='+spec['drive_id']+'&export=download&confirm=t'
        part=target.with_name(target.name+'.part');total=0
        print('Downloading',name,flush=True)
        with urllib.request.urlopen(url,timeout=60) as response,part.open('wb') as output:
            while True:
                block=response.read(1024*1024)
                if not block:break
                if total==0 and not (block.startswith(b'PK') if spec['format']=='zip' else block.startswith(b'\x1f\x8b')):
                    raise RuntimeError('Expected archive; received confirmation/error page')
                total+=len(block)
                if total>4*1024**3:raise RuntimeError('Archive exceeds 4 GiB download cap')
                output.write(block)
        part.rename(target)
        record=dict(spec,url=url,bytes=total,sha256=digest(target),retrieved_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        receipt.write_text(json.dumps(record,indent=2)+'\n')
        print('Downloaded',name,total,record['sha256'],flush=True)
        if spec['format']=='zip':
            with zipfile.ZipFile(target) as archive:
                print('Members:',[(i.filename,i.file_size) for i in archive.infolist() if not i.is_dir()],flush=True)


if __name__=='__main__':main()
