#!/usr/bin/env python3
"""Nine prospectively controlled POW-S attempts; previous cohorts are immutable."""
import argparse
import collections
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import statistics
import subprocess
import time

from benchmark import ROOT, digest, parse_author_phases
from run_extended_suite import classify_exit
from pows_recheck_monitor import snapshot, gate_decision, assess, expand_list

OUT = ROOT / 'results/pows-recheck-20261111'
CONFIG = ROOT / 'configs/pows-recheck-20261111.json'
OLD = ROOT / 'results/supplement-20261110'
BINARY = ROOT / 'build/drivers/sigmod'
DATA = ROOT / 'data/processed/synthetic-POW-S-approx/author-input.hyp_sorted_by_edge_desc_node_asc.txt'


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def save(path, value):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    tmp.replace(path)


def read(path):
    return json.loads(path.read_text())


def record_status(state, **kw):
    save(OUT / 'status.json', dict(state=state, updated_at=now(), coordinator_pid=os.getpid(), **kw))


def guard():
    if ROOT.stat().st_dev == Path('/').stat().st_dev or os.environ.get('TMPDIR') != str(ROOT / '.runtime/tmp'):
        raise RuntimeError('Non-root project environment guard is required')
    for path in [OUT, CONFIG, DATA, BINARY]:
        if not path.resolve().is_relative_to(ROOT) or path.stat().st_dev != ROOT.stat().st_dev:
            raise RuntimeError('Destination or dependency redirects outside project: ' + str(path))


def frozen_sources():
    return {str(p.relative_to(ROOT)): digest(p) for p in [CONFIG, Path(__file__),
            ROOT / 'scripts/pows_recheck_monitor.py', ROOT / 'scripts/benchmark.py',
            ROOT / 'scripts/run_extended_suite.py', ROOT / 'configs/supplement-expected.json',
            OUT / 'preflight.json', OUT / 'numa-probe-corrected.json']}


def initialize(policy):
    target = OUT / 'metadata.json'
    if target.exists():
        meta = read(target)
        if meta['source_sha256'] != frozen_sources():
            raise RuntimeError('Cohort sources changed; inspect checkpoint before continuing')
        return meta
    pre = read(OUT / 'preflight.json')
    if pre['selected']['cpu'] != policy['cpu'] or pre['selected']['sibling_cpu'] != policy['sibling_cpu']:
        raise RuntimeError('CPU selection does not match prospectively recorded preflight')
    if read(OUT / 'numa-probe-corrected.json')['exit_code'] != 0:
        raise RuntimeError('CPU/NUMA binding probe failed')
    topology = Path('/sys/devices/system/cpu') / ('cpu' + str(policy['cpu'])) / 'topology/thread_siblings_list'
    if set(expand_list(topology.read_text())) != {policy['cpu'], policy['sibling_cpu']}:
        raise RuntimeError('SMT topology changed')
    previous = read(OLD / 'experiments/metadata.json')
    reference = read(ROOT / 'configs/supplement-expected.json')['POW-S-approx']
    if digest(BINARY) != previous['binary_sha256']['build/drivers/sigmod']:
        raise RuntimeError('Historical plain binary changed')
    record_status('verifying_input')
    actual = digest(DATA)
    if actual != reference['manifest']['processed']['sha256']:
        raise RuntimeError('Historical input SHA mismatch')
    plan = [dict(x, label=x['label'].replace('pows-ablation-', 'pows-recheck-'), study='pows_recheck')
            for x in previous['plan'] if x['study'] == 'pows_ablation']
    if len(plan) != 9:
        raise RuntimeError('Expected exactly nine planned attempts')
    oldfiles = [OLD / 'audit.json', OLD / 'experiments/metadata.json', OLD / 'experiments/metadata-v2.json']
    oldfiles += [OLD / 'experiments' / (x['label'] + '.json') for x in previous['plan']]
    meta = dict(created_at=now(), plan=plan, policy=policy, policy_sha256=digest(CONFIG),
                source_sha256=frozen_sources(), input_sha256=actual, input_bytes=DATA.stat().st_size,
                binary_sha256=digest(BINARY), historical_core_sha256=reference['core_sha256_values'],
                vertices=reference['manifest']['processed']['vertices'],
                old_evidence_sha256={str(p.relative_to(ROOT)): digest(p) for p in oldfiles},
                cohort_note='Separate nine-attempt cohort. Original 405 and 141 attempts are retained. No outcome-selected replacement or automatic extra attempts.',
                environment_change='Fixed NUMA0 CPU26/SMT90 selected using idle measurements only; observer on CPU63, explicit membind=0, longer quiet gate. Not exclusive CPU/cache/bandwidth ownership.',
                cpu_model=next(x for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('model name')),
                clocksource=Path('/sys/devices/system/clocksource/clocksource0/current_clocksource').read_text().strip())
    save(target, meta)
    return meta


def gate(item, policy):
    good = 0
    started = time.monotonic()
    previous = snapshot(policy, BINARY)
    while good < policy['gate_samples']:
        record_status('waiting_for_quiet_window', label=item['label'], consecutive_good=good,
                      required_samples=policy['gate_samples'], cpu=policy['cpu'])
        if time.monotonic() - started > policy['max_gate_wait_seconds']:
            raise RuntimeError('Quiet window unavailable within one hour; no new attempt launched')
        time.sleep(policy['sample_interval_seconds'])
        current = snapshot(policy, BINARY)
        decision = gate_decision(previous, current, policy)
        good = good + 1 if decision['accepted'] else 0
        with (OUT / 'gate-samples.jsonl').open('a') as f:
            f.write(json.dumps(dict(current, at=now(), label=item['label'], **decision)) + '\n')
        previous = current
    return current


def invoke(item, meta):
    policy = meta['policy']
    label = item['label']
    record = OUT / (label + '.json')
    if record.exists():
        return read(record)
    if any((OUT / (label + suffix)).exists() for suffix in ['.log', '.time.txt', '.monitor.jsonl', '.cores.csv']):
        raise RuntimeError('Interrupted attempt evidence preserved; do not rerun automatically: ' + label)
    if digest(BINARY) != meta['binary_sha256'] or frozen_sources() != meta['source_sha256']:
        raise RuntimeError('Frozen binary or source changed')
    record_status('verifying_input', label=label)
    if digest(DATA) != meta['input_sha256']:
        raise RuntimeError('Input changed')
    if shutil.disk_usage(ROOT).free < meta['vertices'] * 30 + 10 * 1024**3:
        raise RuntimeError('Insufficient space for full core output')
    before = gate(item, policy)
    core = OUT / (label + '.cores.csv')
    command = ['/usr/bin/time', '-v', '-o', str(OUT / (label + '.time.txt')),
               'timeout', '--signal=TERM', '--kill-after=30s', '21600s',
               'taskset', '-c', str(policy['cpu']), 'numactl', '--membind=0',
               str(BINARY), str(DATA), item['argument'], str(core)]
    env = dict(os.environ, OMP_NUM_THREADS='1', OMP_DYNAMIC='FALSE', LC_ALL='C',
               REPRO_TIMER_STRIDE='1', REPRO_TIMER_SEED=str(5012 + item['repeat']))
    def limits():
        resource.setrlimit(resource.RLIMIT_AS, (500 * 1024**3, 500 * 1024**3))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    start = time.monotonic()
    monitor = []
    with (OUT / (label + '.log')).open('x') as log:
        p = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env,
                             start_new_session=True, preexec_fn=limits)
        save(OUT / 'running.json', dict(item, state='running', pid=p.pid,
              coordinator_pid=os.getpid(), command=command, started_at=now(), policy_id=policy['id']))
        record_status('running', label=label, attempt_pid=p.pid, cpu=policy['cpu'])
        try:
            while p.poll() is None:
                x = dict(snapshot(policy, BINARY, p.pid), at=now())
                monitor.append(x)
                with (OUT / (label + '.monitor.jsonl')).open('a') as f:
                    f.write(json.dumps(x) + '\n')
                try:
                    p.wait(timeout=policy['sample_interval_seconds'])
                except subprocess.TimeoutExpired:
                    pass
        except BaseException:
            os.killpg(p.pid, signal.SIGTERM)
            try:
                p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()
            raise
    elapsed = time.monotonic() - start
    monitor.append(dict(snapshot(policy, BINARY), at=now()))
    with (OUT / (label + '.monitor.jsonl')).open('a') as f:
        f.write(json.dumps(monitor[-1]) + '\n')
    text = (OUT / (label + '.log')).read_text()
    status = classify_exit(p.returncode, elapsed, 21600, text, True)
    if status == 'failed' and ('Segmentation fault' in text or p.returncode in [-11, 139]):
        status = 'crash'
    row = dict(item, status=status, exit_code=p.returncode, command=command,
               process_wall_s=elapsed, finished_at=now(), started_environment=before,
               input_sha256=meta['input_sha256'], binary_sha256=meta['binary_sha256'],
               timeout_s=21600, memory_limit_bytes=500 * 1024**3, cpu=policy['cpu'],
               sibling_cpu=policy['sibling_cpu'], numa_memory_node=0,
               load_policy_id=policy['id'], load_policy_sha256=meta['policy_sha256'],
               runner_source_sha256=meta['source_sha256'][str(Path(__file__).relative_to(ROOT))],
               environment={k: env[k] for k in ['OMP_NUM_THREADS', 'OMP_DYNAMIC', 'LC_ALL', 'REPRO_TIMER_STRIDE', 'REPRO_TIMER_SEED']},
               **assess(before, monitor, elapsed, policy))
    if status == 'ok':
        row.update(parse_author_phases(text))
        metrics = [json.loads(x.split(' ', 1)[1]) for x in text.splitlines() if x.startswith('REPRO_METRICS ')]
        if len(metrics) != 1:
            raise RuntimeError('Missing or ambiguous driver metrics')
        row['driver_metrics'] = metrics[0]
        row['core_sha256'] = digest(core)
        row['historical_core_match'] = row['core_sha256'] in meta['historical_core_sha256'] and metrics[0]['vertices'] == meta['vertices']
        if not row['historical_core_match']:
            row['status'] = 'incorrect'
    rss = re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)', (OUT / (label + '.time.txt')).read_text())
    row['peak_rss_kib'] = int(rss.group(1)) if rss else None
    for suffix, key in [('.log', 'log_sha256'), ('.time.txt', 'time_file_sha256'), ('.monitor.jsonl', 'monitor_sha256')]:
        row[key] = digest(OUT / (label + suffix))
    save(record, row)
    print(label, row['status'], row.get('reported_execution_s'), row['load_control_reasons'], flush=True)
    save(OUT / 'running.json', dict(state='attempt_finished', label=label, updated_at=now()))
    if row['status'] == 'incorrect':
        raise RuntimeError('Complete core output mismatch; inspect before further attempts')
    return row


def audit(meta):
    record_status('auditing')
    rows, checks = [], []
    for name, expected in {**meta['source_sha256'], **meta['old_evidence_sha256'],
                           str(BINARY.relative_to(ROOT)): meta['binary_sha256'],
                           str(DATA.relative_to(ROOT)): meta['input_sha256']}.items():
        checks.append({'path': name, 'match': digest(ROOT / name) == expected})
    for item in meta['plan']:
        row = read(OUT / (item['label'] + '.json'))
        assert all(row[k] == v for k, v in item.items())
        for suffix, key in [('.log', 'log_sha256'), ('.time.txt', 'time_file_sha256'), ('.monitor.jsonl', 'monitor_sha256')]:
            checks.append({'label': item['label'], 'kind': key, 'match': digest(OUT / (item['label'] + suffix)) == row[key]})
        if row['status'] == 'ok':
            checks.append({'label': item['label'], 'kind': 'full_core',
                           'match': digest(OUT / (item['label'] + '.cores.csv')) == row['core_sha256'] and row['historical_core_match']})
        monitor = [json.loads(x) for x in (OUT / (item['label'] + '.monitor.jsonl')).read_text().splitlines()]
        assessed = assess(row['started_environment'], monitor, row['process_wall_s'], meta['policy'])
        checks.append({'label': item['label'], 'kind': 'recomputed_load_quality',
                       'match': all(row[k] == v for k, v in assessed.items())})
        checks.append({'label': item['label'], 'kind': 'frozen_controls', 'match':
                       row['input_sha256'] == meta['input_sha256'] and row['binary_sha256'] == meta['binary_sha256']
                       and row['load_policy_sha256'] == meta['policy_sha256'] and row['cpu'] == meta['policy']['cpu']
                       and row['memory_limit_bytes'] == 500 * 1024**3 and row['timeout_s'] == 21600})
        rows.append(row)
    groups = {}
    for arg, name in [('2', 'LB'), ('1', 'RUC'), ('0', 'LB+RUC')]:
        rr = [x for x in rows if x['argument'] == arg]
        assert len(rr) == 3 and {x['repeat'] for x in rr} == {1, 2, 3}
        ok = all(x['status'] == 'ok' and x['historical_core_match'] for x in rr)
        clean = all(x['load_control_pass'] for x in rr)
        group = {'records': [x['label'] for x in rr], 'statuses': dict(collections.Counter(x['status'] for x in rr)),
                 'three_complete_correct_attempts': ok, 'load_control_pass': clean,
                 'eligible_controlled_comparison': ok and clean, 'load_flagged': sum(not x['load_control_pass'] for x in rr)}
        for field in ['reported_init_s', 'reported_execution_s', 'reported_total_s', 'process_wall_s', 'peak_rss_kib']:
            vals = [x.get(field) for x in rr]
            group[field] = {'values': vals, 'mean': statistics.mean(vals) if ok and None not in vals else None,
                            'min': min(vals) if ok and None not in vals else None, 'max': max(vals) if ok and None not in vals else None}
        groups[name] = group
    result = {'created_at': now(), 'records': len(rows), 'planned': 9,
              'statuses': dict(collections.Counter(x['status'] for x in rows)),
              'load_clean': sum(x['load_control_pass'] for x in rows), 'load_flagged': sum(not x['load_control_pass'] for x in rows),
              'all_checks_pass': all(x['match'] for x in checks), 'checks': checks, 'groups': groups,
              'all_groups_eligible': all(g['eligible_controlled_comparison'] for g in groups.values()),
              'note': 'New cohort retained separately. No selected repeats. Environment changed, so time differences from prior cohorts are not an isolated causal load effect.'}
    save(OUT / 'audit.json', result)
    if not result['all_checks_pass']:
        raise RuntimeError('Final audit failed')
    save(OUT / 'records.json', rows)
    save(OUT / 'running.json', {'state': 'complete', 'updated_at': now(), 'records': 9})
    record_status('audited_pending_report', records=9, load_clean=result['load_clean'],
                  load_flagged=result['load_flagged'], all_groups_eligible=result['all_groups_eligible'])
    print(json.dumps({k: result[k] for k in ['records', 'statuses', 'load_clean', 'load_flagged', 'all_checks_pass', 'all_groups_eligible']}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--audit-only', action='store_true')
    args = parser.parse_args()
    guard()
    lock = (OUT / 'workflow.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    (OUT / 'workflow.pid').write_text(str(os.getpid()) + '\n')
    policy = read(CONFIG)
    os.sched_setaffinity(0, {policy['observer_cpu']})
    def stopped(signum, frame):
        raise InterruptedError('signal ' + str(signum))
    signal.signal(signal.SIGTERM, stopped)
    signal.signal(signal.SIGINT, stopped)
    try:
        meta = initialize(policy)
        if not args.audit_only:
            for item in meta['plan']:
                invoke(item, meta)
        audit(meta)
    except BaseException as error:
        record_status('needs_attention', error=repr(error))
        raise


if __name__ == '__main__':
    main()
