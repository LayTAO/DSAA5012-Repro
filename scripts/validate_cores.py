#!/usr/bin/env python3
"""Validate an exported vertex,core CSV against a small hypergraph oracle."""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from repro.oracle import core_numbers, read_hyp


def read_core_csv(path):
    cores = {}
    with Path(path).open(newline="", encoding="utf-8") as stream:
        rows = csv.DictReader(stream)
        if rows.fieldnames != ["vertex", "core"]:
            raise ValueError("Expected exactly the CSV columns: vertex,core")
        for row in rows:
            vertex, core = int(row["vertex"]), int(row["core"])
            if vertex in cores:
                raise ValueError("Duplicate vertex in output: " + str(vertex))
            if core < 0:
                raise ValueError("Negative core number for vertex " + str(vertex))
            cores[vertex] = core
    return cores


def compare(expected, actual):
    missing = sorted(expected.keys() - actual.keys())
    extra = sorted(actual.keys() - expected.keys())
    mismatches = [
        {"vertex": vertex, "expected": expected[vertex], "actual": actual[vertex]}
        for vertex in sorted(expected.keys() & actual.keys())
        if expected[vertex] != actual[vertex]
    ]
    return {
        "passed": not (missing or extra or mismatches),
        "expected_vertices": len(expected),
        "actual_vertices": len(actual),
        "missing_count": len(missing),
        "extra_count": len(extra),
        "mismatch_count": len(mismatches),
        "missing_sample": missing[:20],
        "extra_sample": extra[:20],
        "mismatch_sample": mismatches[:20],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hypergraph", type=Path)
    parser.add_argument("core_csv", type=Path)
    args = parser.parse_args()
    expected = core_numbers(read_hyp(args.hypergraph))
    actual = read_core_csv(args.core_csv)
    result = compare(expected, actual)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
