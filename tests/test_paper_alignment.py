import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from benchmark import parse_author_phases
from prepare_cornell import canonicalize, unique_stats_and_vertices


class AlignmentTests(unittest.TestCase):
    def test_author_clocks_are_kept_distinct(self):
        sigmod = parse_author_phases('init_Time: 0.2 s\nexc_Time: 0.03 s\n')
        baseline = parse_author_phases('VLDB_CPU_PHASES {"init_cpu_s": 0.5, "iteration_cpu_s": 0.07}\n')
        self.assertAlmostEqual(sigmod['reported_total_s'], .23)
        self.assertAlmostEqual(baseline['reported_total_s'], .57)
        self.assertNotEqual(sigmod['reported_clock'], baseline['reported_clock'])
        with self.assertRaises(ValueError):
            parse_author_phases('init_Time: 0.2 s\n')

    def test_duplicates_singletons_and_sparse_ids(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'sizes').write_text('3\n2\n1\n1\n')
            (root/'ids').write_text('9\n2\n2\n2\n9\n7\n2\n')
            metadata = canonicalize(root/'sizes', root/'ids', root/'out')
            lines = sorted(set((root/'out').read_text().splitlines()))
            (root/'unique').write_text('\n'.join(lines)+'\n')
            stats, kept = unique_stats_and_vertices(root/'unique')
            self.assertEqual(metadata['duplicate_members_removed'], 1)
            self.assertEqual(stats['unique_vertices'], 3)
            self.assertEqual(stats['unique_edges'], 3)
            self.assertEqual(stats['singleton_edges'], 2)
            self.assertEqual(kept, {2, 9})
            self.assertEqual(stats['upstream_array_nodes'], 10)
            self.assertEqual(stats['upstream_array_edges'], 5)

    def test_truncated_input_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'sizes').write_text('3\n')
            (root/'ids').write_text('1\n2\n')
            with self.assertRaises(ValueError):
                canonicalize(root/'sizes', root/'ids', root/'out')

    def test_ordered_dedup_preserves_permuted_records(self):
        # Deduplicating sets before the author's org command loses a record.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'sizes').write_text('3\n2\n1\n1\n')
            (root/'ids').write_text('9\n2\n2\n2\n9\n7\n2\n')
            canonicalize(root/'sizes', root/'ids', root/'out', ordered=True)
            records=set((root/'out').read_text().splitlines())
            self.assertEqual(records, {'9,2','2,9','7','2'})


if __name__ == '__main__':
    unittest.main()
