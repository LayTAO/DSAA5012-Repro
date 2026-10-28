"""Check the oracle against exhaustive induced-subhypergraph enumeration."""

import itertools
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from repro.oracle import core_numbers
from validate_cores import compare


def exhaustive_cores(edges, vertices):
    result = dict.fromkeys(vertices, 0)
    for size in range(1, len(vertices) + 1):
        for subset in itertools.combinations(vertices, size):
            active = set(subset)
            retained = [set(edge) for edge in edges if set(edge).issubset(active)]
            counts = []
            for vertex in subset:
                others = set()
                for edge in retained:
                    if vertex in edge:
                        others |= edge
                others.discard(vertex)
                counts.append(len(others))
            minimum = min(counts)
            for vertex in subset:
                result[vertex] = max(result[vertex], minimum)
    return result


class OracleTests(unittest.TestCase):
    def test_single_edge_and_isolated_vertex(self):
        self.assertEqual(core_numbers([{1, 2, 3, 4}], {0, 1, 2, 3, 4}),
                         {0: 0, 1: 3, 2: 3, 3: 3, 4: 3})

    def test_multiple_core_levels(self):
        self.assertEqual(core_numbers([{1, 2, 3}, {3, 4}]),
                         {1: 2, 2: 2, 3: 2, 4: 1})

    def test_strong_induction_differs_from_clique_projection(self):
        # A clique projection retains a K4 on 1..4 after removing 5 and 6.
        # Strong induction deletes the two three-vertex edges entirely,
        # leaving only a cycle; no vertex belongs to a 3-core.
        edges = [{1, 2}, {2, 3}, {3, 4}, {4, 1}, {1, 3, 5}, {2, 4, 6}]
        self.assertEqual(core_numbers(edges), dict.fromkeys(range(1, 7), 2))

    def test_duplicate_edges_do_not_inflate_neighbors(self):
        edges = [{1, 2, 3}, {1, 2, 3}, {3, 4}, {4}]
        self.assertEqual(core_numbers(edges), core_numbers(edges[:1] + [{3, 4}]))

    def test_empty(self):
        self.assertEqual(core_numbers([]), {})
        self.assertEqual(core_numbers([], {1, 2}), {1: 0, 2: 0})

    def test_random_inputs_against_all_induced_subhypergraphs(self):
        generator = random.Random(5012)
        for trial in range(120):
            vertices = list(range(generator.randint(1, 7)))
            edges = [generator.sample(vertices, generator.randint(1, len(vertices)))
                     for _ in range(generator.randint(0, 15))]
            with self.subTest(trial=trial):
                self.assertEqual(core_numbers(edges, vertices),
                                 exhaustive_cores(edges, vertices))

    def test_size_guard(self):
        with self.assertRaises(ValueError):
            core_numbers([range(129)])

    def test_comparator_checks_ids_and_values(self):
        report = compare({1: 2, 2: 2, 3: 1}, {1: 2, 2: 1, 4: 1})
        self.assertFalse(report['passed'])
        self.assertEqual(report['missing_count'], 1)
        self.assertEqual(report['extra_count'], 1)
        self.assertEqual(report['mismatch_count'], 1)
        self.assertTrue(compare({1: 2}, {1: 2})['passed'])


if __name__ == '__main__':
    unittest.main()
