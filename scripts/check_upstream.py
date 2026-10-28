#!/usr/bin/env python3
"""Exercise unmodified upstream kernels against an independent small-graph oracle."""
import argparse
import csv
import json
from pathlib import Path
import random
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from repro.oracle import core_numbers


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--random-cases", type=int, default=100)
    parser.add_argument("--seed", type=int, default=5012)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    cases = [
        [[3], [7, 9], [3, 9]], [[11], [21]],
        [[1]], [[1, 2]], [[1, 2, 3, 4]], [[1], [2], [3]],
        [[1, 2], [1, 2], [2, 3]],
        [[1, 2], [2, 3], [3, 4], [4, 1], [1, 3, 5], [2, 4, 6]],
    ]
    rng = random.Random(args.seed)
    for _ in range(args.random_cases):
        n = rng.randint(2, 12)
        edges = [[v] for v in range(1, n + 1)]
        edges += [rng.sample(range(1, n + 1), rng.randint(1, n))
                  for _ in range(rng.randint(1, 24))]
        cases.append(edges)
    methods = [("sigmod", str(i)) for i in range(7)] + [("vldb", "OPTIV")]
    failures = []
    checks = 0
    for index, edges in enumerate(cases):
        stem = args.output / ("case_%03d" % index)
        hyp = stem.with_suffix(".hyp")
        hyp.write_text("\n".join(",".join(map(str, sorted(set(e)))) for e in edges))
        expected = core_numbers(edges)
        for binary, algorithm in methods:
            checks += 1
            label = binary + "_" + algorithm
            core_path = args.output / (stem.name + "_" + label + ".csv")
            log_path = core_path.with_suffix(".log")
            error = None
            try:
                run = subprocess.run([str(ROOT / "build/drivers" / binary), str(hyp),
                                      algorithm, str(core_path)], capture_output=True,
                                     text=True, timeout=20, check=False)
                log_path.write_text(run.stdout + run.stderr)
                if run.returncode:
                    error = "exit=" + str(run.returncode)
                else:
                    with core_path.open() as stream:
                        rows = list(csv.DictReader(stream))
                    actual = {int(row["vertex"]): int(row["core"]) for row in rows}
                    if len(rows) != len(actual) or actual != expected:
                        error = {"expected": expected, "actual": actual}
            except (subprocess.TimeoutExpired, OSError, ValueError) as exception:
                error = str(exception)
            if error is not None:
                failures.append({"case": index, "method": label, "error": error})
    summary = {"seed": args.seed, "cases": len(cases), "checks": checks,
               "passed": checks - len(failures), "failures": failures}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
