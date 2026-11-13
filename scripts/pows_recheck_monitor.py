"""CPU-local monitoring for a separately frozen POW-S cohort; no system mutation."""
import os
import re
import time
from pathlib import Path


def expand_list(text):
    values = []
    for chunk in text.strip().split(','):
        a, sep, b = chunk.partition('-')
        values.extend(range(int(a), int(b) + 1) if sep else [int(a)])
    return values


def algorithm_task(pid, binary):
    for _ in range(8):
        try:
            folder = Path('/proc') / str(pid)
            exe = (folder / 'cmdline').read_bytes().split(b'\0')[0].decode()
            if exe == str(binary):
                text = (folder / 'stat').read_text()
                stat = text[text.rfind(')') + 2:].split()
                status = (folder / 'status').read_text()
                result = {'pid': pid, 'start_ticks': int(stat[19]),
                          'cpu_ticks': int(stat[11]) + int(stat[12]),
                          'last_cpu': int(stat[36]), 'threads': int(stat[17]),
                          'allowed_cpus': re.search(r'Cpus_allowed_list:\s*([^\n]+)', status).group(1).strip()}
                try:
                    ss = (folder / 'schedstat').read_text().split()
                    result['scheduled_runtime_ns'] = int(ss[0])
                    result['runqueue_delay_ns'] = int(ss[1])
                except (OSError, ValueError, IndexError):
                    pass
                return result
            children = (folder / 'task' / str(pid) / 'children').read_text().split()
            if len(children) != 1:
                return None
            pid = int(children[0])
        except (OSError, ValueError, IndexError, AttributeError):
            return None
    return None


def snapshot(policy, binary, pid=None):
    wanted = {'cpu' + str(n) for n in policy['node_cpus']}
    cpu = {}
    for line in Path('/proc/stat').read_text().splitlines():
        z = line.split()
        if z and z[0] in wanted:
            v = list(map(int, z[1:9]))
            cpu[z[0]] = {'total': sum(v), 'idle': v[3] + v[4]}
    pressure = {}
    for name, kind in [('cpu', 'some'), ('memory', 'some'), ('io', 'full')]:
        for line in (Path('/proc/pressure') / name).read_text().splitlines():
            z = line.split()
            if z[0] == kind:
                pressure[name + '_pressure_' + kind + '_avg10_pct'] = float(dict(v.split('=') for v in z[1:])['avg10'])
    return dict(monotonic_s=time.monotonic(), cpu=cpu, load=os.getloadavg(),
                memavailable_kib=int(re.search(r'MemAvailable:\s+(\d+)', Path('/proc/meminfo').read_text()).group(1)),
                algorithm_task=algorithm_task(pid, binary) if pid else None, **pressure)


def busy(a, b, keys):
    total = sum(b['cpu'][k]['total'] - a['cpu'][k]['total'] for k in keys)
    idle = sum(b['cpu'][k]['idle'] - a['cpu'][k]['idle'] for k in keys)
    return 100 * (1 - idle / total) if total > 0 else None


def system_reasons(x, policy, before=False):
    limits = policy['before'] if before else policy['during']
    reasons = []
    if x['load'][0] > limits['max_load1']:
        reasons.append('global_load')
    for key in ['cpu_pressure_some_avg10_pct', 'memory_pressure_some_avg10_pct', 'io_pressure_full_avg10_pct']:
        if x[key] > limits['max_' + key]:
            reasons.append(key)
    if x['memavailable_kib'] <= limits['min_memory_available_gib'] * 1024**2:
        reasons.append('available_memory')
    return reasons


def gate_decision(a, b, policy):
    reasons = system_reasons(b, policy, before=True)
    metrics = {'selected_cpu_busy_pct': busy(a, b, ['cpu' + str(policy['cpu'])]),
               'sibling_busy_pct': busy(a, b, ['cpu' + str(policy['sibling_cpu'])]),
               'node_busy_pct': busy(a, b, a['cpu'])}
    for key, limit in [('selected_cpu_busy_pct', 'max_cpu_busy_pct'),
                       ('sibling_busy_pct', 'max_sibling_busy_pct'), ('node_busy_pct', 'max_node_busy_pct')]:
        if metrics[key] is None or metrics[key] > policy['before'][limit]:
            reasons.append(key)
    return dict(metrics, accepted=not reasons, reasons=reasons)


def assess(before, monitor, elapsed, policy, clock_ticks=None):
    clock_ticks = clock_ticks or os.sysconf('SC_CLK_TCK')
    reasons = set()
    sibling, node, other = [], [], []
    coverage = 0.0
    task_samples = []
    for x in monitor:
        reasons.update(system_reasons(x, policy))
        task = x.get('algorithm_task')
        if task:
            task_samples.append(task)
            if task['last_cpu'] != policy['cpu'] or task['allowed_cpus'] != str(policy['cpu']):
                reasons.add('cpu_binding_violation')
            if task['threads'] != 1:
                reasons.add('thread_count_violation')
    for a, b in zip([before, *monitor], monitor):
        dt = b['monotonic_s'] - a['monotonic_s']
        if dt < policy['minimum_cpu_interval_seconds']:
            continue
        sibling.append(busy(a, b, ['cpu' + str(policy['sibling_cpu'])]))
        node.append(busy(a, b, a['cpu']))
        x, y = a.get('algorithm_task'), b.get('algorithm_task')
        if x and y and (x['pid'], x['start_ticks']) == (y['pid'], y['start_ticks']):
            own = (y['cpu_ticks'] - x['cpu_ticks']) / clock_ticks / dt * 100
            measured = busy(a, b, ['cpu' + str(policy['cpu'])])
            if measured is not None:
                other.append(max(0, measured - own))
                coverage += dt
    limits = policy['during']
    if not sibling or any(v is None for v in sibling) or max(sibling) > limits['max_sibling_busy_pct']:
        reasons.add('sibling_busy_or_unobserved')
    if not node or any(v is None for v in node) or max(node) > limits['max_node_busy_pct']:
        reasons.add('node_busy_or_unobserved')
    fraction = min(1, coverage / elapsed) if elapsed else 0
    if fraction < limits['min_cpu_observation_fraction']:
        reasons.add('cpu_observation_incomplete')
    if other and max(other) > limits['max_other_cpu_busy_pct']:
        reasons.add('other_activity_on_selected_cpu')
    return {'load_control_pass': not reasons, 'load_control_reasons': sorted(reasons),
            'load_max': max(x['load'][0] for x in monitor),
            'sibling_busy_max_pct': max((v for v in sibling if v is not None), default=None),
            'node_busy_max_pct': max((v for v in node if v is not None), default=None),
            'other_cpu_busy_max_pct': max(other, default=None), 'cpu_observation_fraction': fraction,
            'algorithm_samples': len(task_samples),
            'observed_last_cpu_values': sorted({t['last_cpu'] for t in task_samples}),
            'observed_thread_counts': sorted({t['threads'] for t in task_samples}),
            'last_observed_runqueue_delay_ns': task_samples[-1].get('runqueue_delay_ns') if task_samples else None,
            'interpretation': 'Whole-process finite monitoring, not exclusive resources or phase-specific causal attribution.'}
