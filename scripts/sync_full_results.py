#!/usr/bin/env python3
"""Download the bounded metadata package and refresh local scientific comparisons."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',required=True);parser.add_argument('--remote-root',required=True)
    parser.add_argument('--output',type=Path,default=ROOT/'reports/full-comparison');args=parser.parse_args()
    if args.host.startswith('-') or not args.remote_root.startswith('/'):parser.error('Invalid host/root')
    out=args.output.resolve()
    if not out.is_relative_to(ROOT/'reports'):parser.error('Keep local summaries under project reports')
    command='cd '+shlex.quote(args.remote_root)+' && bash scripts/run_on_server.sh python3 scripts/export_full_results.py'
    result=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8',args.host,command],stdout=subprocess.PIPE,check=True,timeout=120)
    if len(result.stdout)>32*1024**2:raise RuntimeError('Metadata package exceeds size limit')
    package=json.loads(result.stdout);target=out/'input';target.mkdir(parents=True,exist_ok=True)
    for name,content in package.items():
        path=(target/name).resolve()
        if not path.is_relative_to(target) or not isinstance(content,str) or len(content.encode())>2*1024**2:raise RuntimeError('Invalid metadata item')
        if path.suffix not in ['.json','.jsonl']:raise RuntimeError('Refusing a non-metadata file')
    previous=target/'export-manifest.json'
    if previous.exists():
        stale=set(json.loads(previous.read_text())['files'])-set(package)
        if stale:raise RuntimeError('Remote metadata was removed; preserve and inspect stale local records before syncing: '+repr(sorted(stale)))
    for name,content in package.items():
        path=target/name;path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_suffix(path.suffix+'.tmp')
        temporary.write_text(content);temporary.replace(path)
    previous.write_text(json.dumps({'exported_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'bytes':len(result.stdout),'files':sorted(package)},indent=2)+'\n')
    environment=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',MPLCONFIGDIR=str(ROOT/'.runtime/matplotlib'))
    subprocess.run([sys.executable,str(ROOT/'scripts/summarize_full_results.py'),str(target),'--output',str(out/'summary.json')],env=environment,check=True)
    subprocess.run([sys.executable,str(ROOT/'scripts/plot_full_results.py'),str(out/'summary.json'),'--input',str(target),'--output',str(out)],env=environment,check=True)

if __name__=='__main__':main()
