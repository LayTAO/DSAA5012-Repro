#!/usr/bin/env python3
"""Download and audit Cornell inputs, preserving raw data and every transformation."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request
from benchmark import ROOT, digest, input_stats


def download_archive(spec, base):
    destination = base / (spec['name'] + '.tar.gz')
    if destination.exists():
        return destination
    url = 'https://drive.usercontent.google.com/download?id=' + spec['drive_id'] + '&export=download&confirm=t'
    part = destination.with_suffix(destination.suffix + '.part')
    with urllib.request.urlopen(url, timeout=60) as response:
        first = response.read(8192)
        if first[:2] != b'\x1f\x8b':
            raise RuntimeError('Expected gzip data; received a confirmation or error page')
        with part.open('wb') as output:
            output.write(first)
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                output.write(block)
                if output.tell() > 4 * 1024 ** 3:
                    raise RuntimeError('Archive exceeds the 4 GiB limit for this first batch')
    part.rename(destination)
    return destination


def canonicalize(nverts, simplices, output, ordered=False):
    count = incidences = removed_members = 0
    with nverts.open() as sizes, simplices.open() as ids, output.open('w') as result:
        for line in sizes:
            size = int(line)
            if size < 0:
                raise ValueError('Negative edge size')
            edge = []
            for _ in range(size):
                node = ids.readline()
                if not node:
                    raise ValueError('Truncated simplex stream')
                edge.append(int(node))
            canonical = list(dict.fromkeys(edge)) if ordered else sorted(set(edge))
            removed_members += size - len(canonical)
            incidences += len(canonical)
            count += 1
            if not canonical:
                raise ValueError('Empty simplex needs an explicit handling policy')
            result.write(','.join(map(str, canonical)) + '\n')
        if ids.read().strip():
            raise ValueError('Unexpected extra simplex IDs')
    return dict(timestamped_simplices=count, incidences_before_edge_dedup=incidences,
                duplicate_members_removed=removed_members)


def unique_stats_and_vertices(path):
    all_nodes, kept_nodes = set(), set()
    edges = incidences = singleton_edges = maximum = 0
    with path.open() as stream:
        for line in stream:
            edge = tuple(map(int, line.strip().split(',')))
            all_nodes.update(edge)
            edges += 1
            incidences += len(edge)
            maximum = max(maximum, len(edge))
            if len(edge) == 1:
                singleton_edges += 1
            else:
                kept_nodes.update(edge)
    stats = dict(unique_vertices=len(all_nodes), max_vertex_id=max(all_nodes), min_vertex_id=min(all_nodes),
                 unique_edges=edges, incidences=incidences, singleton_edges=singleton_edges,
                 vertices_after_singleton_removal=len(kept_nodes), edges_after_singleton_removal=edges-singleton_edges,
                 max_edge_size=maximum, upstream_array_nodes=max(all_nodes)+1,
                 upstream_array_edges=edges+2)
    return stats, kept_nodes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', choices=['HI', 'GE', 'CO', 'DF'])
    args = parser.parse_args()
    if os.environ.get('TMPDIR') != str(ROOT / '.runtime/tmp'):
        raise RuntimeError('Run through scripts/run_on_server.sh')
    if shutil.disk_usage(ROOT).free < 30 * 1024 ** 3:
        raise RuntimeError('At least 30 GiB free space required for this batch')
    spec = json.loads((ROOT / 'configs/cornell-datasets.json').read_text())[args.dataset]
    base = ROOT / 'data/raw/cornell'
    base.mkdir(exist_ok=True)
    archive = download_archive(spec, base)
    directory = ROOT / 'data/processed' / ('cornell-' + args.dataset + '-ordered')
    if (directory / 'manifest.json').exists():
        print((directory / 'manifest.json').read_text())
        return
    directory.mkdir(exist_ok=True)
    members = {}
    with tarfile.open(archive, 'r:gz') as tar:
        for member in tar:
            for kind in ['nverts', 'simplices']:
                if member.isfile() and member.name.endswith('-' + kind + '.txt'):
                    if kind in members:
                        raise RuntimeError('Ambiguous archive layout')
                    target = directory / (kind + '.txt')
                    with tar.extractfile(member) as source, target.open('wb') as output:
                        shutil.copyfileobj(source, output)
                    members[kind] = target
    if set(members) != {'nverts', 'simplices'}:
        raise RuntimeError('Missing nverts or simplices file')
    canonical = directory / 'timestamped-canonical.hyp'
    temporal = canonicalize(members['nverts'], members['simplices'], canonical, ordered=True)
    unique = directory / 'unique-including-singletons.hyp'
    environment = dict(os.environ, LC_ALL='C')
    subprocess.run(['sort', '--parallel=2', '-S', '256M', '-T', os.environ['TMPDIR'],
                    '-u', str(canonical), '-o', str(unique)], env=environment, check=True)
    stats, kept_nodes = unique_stats_and_vertices(unique)
    # Match the observed Table 4 convention: deduplicate ordered simplex records
    # before the author's org tool sorts members and drops singleton edges.
    # Keep original ID gaps: org maps IDs before singleton removal.
    working = directory / 'author-input.hyp'
    shutil.copyfile(unique, working)
    binary = ROOT / 'build/native/HypergraphKCore'
    commands = [[str(binary), str(working), 'org'],
                [str(binary), str(working), 'sortEV', 'desc', 'asc']]
    with (directory / 'preprocessing.log').open('w') as output:
        for command in commands:
            subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, check=True, timeout=3600)
    processed = Path(str(working) + '_sorted_by_edge_desc_node_asc.txt')
    profile = json.loads((ROOT / 'configs/paper-profile.json').read_text())
    reported = next(row for row in profile['datasets'] if row['id'] == args.dataset)
    match = {'true_counts_match': stats['unique_vertices']==reported['reported_n'] and stats['unique_edges']==reported['reported_m'],
             'upstream_array_counts_match': stats['upstream_array_nodes']==reported['reported_n'] and stats['upstream_array_edges']==reported['reported_m']}
    result = {'candidate_paper_id': args.dataset, 'source': spec, 'archive_sha256': digest(archive),
              'archive_bytes': archive.stat().st_size, 'temporal': temporal, 'unique': stats,
              'paper_table4': reported, 'paper_count_match': match,
              'preprocessing': 'deduplicate ordered timestamped vertex lists; author org (sort members, drop singleton edges, map IDs before dropping); author sortEV desc asc; preserve resulting ID gaps',
              'processed': input_stats(processed, allow_sparse=True), 'commands': commands}
    if args.dataset == 'HI':
        bundled = ROOT / 'external/hyper-k-core/datasets/coauth-MAG-History-full.hyp'
        reference = directory / 'bundled-canonical.hyp'
        subprocess.run(['sort', '-T', os.environ['TMPDIR'], '-u', str(bundled), '-o', str(reference)], env=environment, check=True)
        candidate = directory / 'converted-canonical.hyp'
        subprocess.run(['sort', '-T', os.environ['TMPDIR'], '-u', str(working), '-o', str(candidate)], env=environment, check=True)
        result['bundled_equivalence'] = {'canonical_text_equal_without_graph_isomorphism_test': digest(reference)==digest(candidate),
                                        'bundled_canonical_sha256': digest(reference), 'converted_canonical_sha256': digest(candidate)}
    (directory / 'manifest.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
