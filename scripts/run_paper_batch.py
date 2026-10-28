#!/usr/bin/env python3
"""Run audited paper datasets with explicit provenance and alignment qualifications."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from benchmark import ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--datasets', nargs='+', default=['HI','CO','DB','AM'])
    parser.add_argument('--run-id', default='001')
    parser.add_argument('--memory-gib', type=int)
    args = parser.parse_args()
    if not args.run_id.isalnum():
        parser.error('Run ID must be alphanumeric')
    if os.environ.get('TMPDIR') != str(ROOT / '.runtime/tmp'):
        raise RuntimeError('Run through scripts/run_on_server.sh')
    registry = json.loads((ROOT/'configs/paper-batch.json').read_text())
    for dataset in args.datasets:
        directory = ROOT / 'data/processed' / registry[dataset]['directory']
        manifest = json.loads((directory/'manifest.json').read_text())
        matched = any(manifest['paper_count_match'].values())
        if not matched:
            source = manifest.get('source', {})
            allowed = registry[dataset]['alignment'] == 'original_baseline_release_edges_match_vertex_layout_differs'
            raw, paper = manifest.get('raw', {}), manifest['paper_table4']
            matched = (allowed and source.get('archive_url') == 'https://drive.google.com/file/d/12cvz-XtfQUbmj-gqlT9z4DKGMuhqLGjs/view'
                       and manifest['raw_upstream_array_edges'] == paper['reported_m']
                       and round(raw['incidences']/raw['edges'], 1) == paper['edge_size_mean'])
        if not matched:
            raise RuntimeError(dataset + ': input violates the reviewed data alignment contract')
    for dataset in args.datasets:
        directory = ROOT / 'data/processed' / registry[dataset]['directory']
        output = ROOT / 'results' / ('paper-' + dataset + '-' + args.run_id)
        if output.exists():
            raise RuntimeError('Output already exists: ' + str(output))
        log = ROOT / 'results' / ('paper-' + dataset + '-' + args.run_id + '.batch.log')
        command = ['python3', str(ROOT/'scripts/benchmark.py'),
                   str(directory/'author-input.hyp_sorted_by_edge_desc_node_asc.txt'),
                   '--profile','paper','--allow-sparse','--memory-gib',str(args.memory_gib or registry[dataset]['memory_gib']),
                   '--output',str(output)]
        print('Starting paper profile:', dataset, flush=True)
        with log.open('w') as stream:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            print(log.read_text()[-4000:], flush=True)
            raise SystemExit(result.returncode)
        (output/'data-alignment.json').write_text(json.dumps(registry[dataset],indent=2)+'\n')
        summary = json.loads((output/'summary.json').read_text())
        print(dataset, json.dumps([{'method':m['method'], 'n':m['successful_runs'],
                                    'reported_total_mean_s':m['reported_total_s']['mean'],
                                    'reported_execution_mean_s':m['reported_execution_s']['mean'],
                                    'rss_mean_kib':m['peak_rss_kib']['mean']} for m in summary['methods']]), flush=True)


if __name__ == '__main__':
    main()
