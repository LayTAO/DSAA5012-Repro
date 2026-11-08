import importlib.util
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from run_extended_suite import classify_exit,parse_stats


class ExtendedRunnerTests(unittest.TestCase):
    def test_kill_is_not_automatically_a_timeout(self):
        self.assertEqual(classify_exit(137,20,21600,''),'failed')
        self.assertEqual(classify_exit(137,21631,21600,''),'timeout')
        self.assertEqual(classify_exit(124,21600,21600,''),'timeout')

    def test_failures_do_not_become_measurements(self):
        self.assertEqual(classify_exit(2,10,21600,'std::bad_alloc'),'memory_limit')
        self.assertEqual(classify_exit(2,10,21600,'UPSTREAM_UNSUPPORTED: zero average'),'unsupported')
        self.assertEqual(classify_exit(124,21600,21600,'REPRO_METRICS {}',True),'export_failed')

    def test_statistics_use_total_execution_denominator(self):
        value=parse_stats('1,120,40\n2,60,0\ndecide_time: 0.25 s\ncompute_time: 0.50 s\nexc_Time: 1.0 s\n')
        self.assertEqual(value['ruc_fraction_of_execution'],0.25)
        self.assertEqual(value['iteration_trace'][1],{'iteration':2,'computed':60,'changed':0})
        self.assertNotIn('ruc_fraction_of_execution',parse_stats('decide_time: 0 s\nexc_Time: 0 s\n'))

if __name__=='__main__':unittest.main()
