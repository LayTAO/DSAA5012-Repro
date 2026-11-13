"""Check decisions against physical scenarios, without executing an experiment."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from pows_recheck_monitor import assess, gate_decision


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads((ROOT / 'configs/pows-recheck-20261111.json').read_text())

    def sample(self, t, own=True, sibling_busy=0, own_pct=100, cpu_pct=100):
        cpu = {'cpu' + str(n): {'total': 10000 + int(t * 100), 'idle': 9000 + int(t * 100)}
               for n in self.policy['node_cpus']}
        cpu['cpu26']['idle'] = 9000 + int(t * (100 - cpu_pct))
        cpu['cpu90']['idle'] = 9000 + int(t * (100 - sibling_busy))
        task = {'pid': 10, 'start_ticks': 100, 'cpu_ticks': int(t * own_pct),
                'last_cpu': 26, 'threads': 1, 'allowed_cpus': '26'} if own else None
        return {'monotonic_s': t, 'cpu': cpu, 'load': [12, 12, 12],
                'memavailable_kib': 800 * 1024**2, 'cpu_pressure_some_avg10_pct': 0,
                'memory_pressure_some_avg10_pct': 0, 'io_pressure_full_avg10_pct': 0,
                'algorithm_task': task}

    def test_own_full_cpu_use_is_not_background_contention(self):
        a, b, c = [self.sample(t) for t in (0, 5, 10)]
        q = assess(a, [b, c], 10, self.policy, 100)
        self.assertTrue(q['load_control_pass'])
        self.assertEqual(q['other_cpu_busy_max_pct'], 0)

    def test_smt_interference_fails_despite_low_global_load(self):
        a, b, c = [self.sample(t, sibling_busy=30) for t in (0, 5, 10)]
        q = assess(a, [b, c], 10, self.policy, 100)
        self.assertIn('sibling_busy_or_unobserved', q['load_control_reasons'])

    def test_same_cpu_other_work_is_detected(self):
        a, b, c = [self.sample(t, own_pct=60, cpu_pct=95) for t in (0, 5, 10)]
        q = assess(a, [b, c], 10, self.policy, 100)
        self.assertAlmostEqual(q['other_cpu_busy_max_pct'], 35)
        self.assertIn('other_activity_on_selected_cpu', q['load_control_reasons'])

    def test_missing_process_observation_cannot_pass(self):
        a, b, c = [self.sample(t, own=False) for t in (0, 5, 10)]
        q = assess(a, [b, c], 10, self.policy, 100)
        self.assertIn('cpu_observation_incomplete', q['load_control_reasons'])

    def test_binding_and_thread_count_are_part_of_acceptance(self):
        a, b, c = [self.sample(t) for t in (0, 5, 10)]
        b['algorithm_task'].update(last_cpu=90, threads=2)
        q = assess(a, [b, c], 10, self.policy, 100)
        self.assertIn('cpu_binding_violation', q['load_control_reasons'])
        self.assertIn('thread_count_violation', q['load_control_reasons'])

    def test_launch_gate_and_runtime_memory_have_distinct_limits(self):
        a, b, c = [self.sample(t, cpu_pct=0) for t in (0, 5, 10)]
        b['memavailable_kib'] = c['memavailable_kib'] = 500 * 1024**2
        self.assertIn('available_memory', gate_decision(a, b, self.policy)['reasons'])
        q = assess(a, [b, c], 10, self.policy, 100)
        self.assertNotIn('available_memory', q['load_control_reasons'])

    def test_io_pressure_failure_is_preserved(self):
        a, b, c = [self.sample(t) for t in (0, 5, 10)]
        b['io_pressure_full_avg10_pct'] = 7
        q = assess(a, [b, c], 10, self.policy, 100)
        self.assertIn('io_pressure_full_avg10_pct', q['load_control_reasons'])

    def test_idle_window_can_pass(self):
        a, b = [self.sample(t, cpu_pct=3, sibling_busy=3) for t in (0, 5)]
        self.assertTrue(gate_decision(a, b, self.policy)['accepted'])


if __name__ == '__main__':
    unittest.main()
