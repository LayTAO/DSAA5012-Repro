#!/usr/bin/env python3
"""Fetch the two version-locked public archives directly into the server project."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import urllib.request
from benchmark import ROOT, digest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',choices=['HI','baseline'])
    args=parser.parse_args()
    if os.environ.get('TMPDIR')!=str(ROOT/'.runtime/tmp'):
        raise RuntimeError('Run on the server through scripts/run_on_server.sh')
    spec=json.loads((ROOT/'configs/data.lock.json').read_text())[args.source]
    target=(ROOT/spec['relative_path']).resolve()
    if not target.is_relative_to((ROOT/'data/raw').resolve()):
        raise RuntimeError('Download target must remain inside data/raw')
    if target.exists():
        if target.stat().st_size!=spec['bytes'] or digest(target)!=spec['sha256']:
            raise RuntimeError('Existing archive differs from the lock; refusing to overwrite it')
        print('Verified existing archive:',target)
        return
    if shutil.disk_usage(ROOT).free<spec['bytes']+5*1024**3:
        raise RuntimeError('Not enough free project disk space')
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=target.with_suffix(target.suffix+'.part')
    total=0; checksum=hashlib.sha256()
    with urllib.request.urlopen(spec['url'],timeout=60) as response,temporary.open('wb') as output:
        while True:
            block=response.read(1024*1024)
            if not block:break
            total+=len(block)
            if total>spec['bytes']:
                raise RuntimeError('Download exceeds the expected archive size')
            checksum.update(block);output.write(block)
    if total!=spec['bytes'] or checksum.hexdigest()!=spec['sha256']:
        raise RuntimeError('Archive checksum mismatch; partial file retained for inspection')
    temporary.rename(target)
    print('Downloaded and verified:',target)


if __name__=='__main__':
    main()
