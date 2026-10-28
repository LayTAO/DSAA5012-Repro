#!/usr/bin/env python3
"""Validate full core outputs, then benchmark fresh single-thread processes."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import random
import re
import resource
import signal
import statistics
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    checksum = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def input_stats(path, allow_sparse=False):
    vertices = set()
    edges = incidences = maximum_edge = 0
    with path.open() as stream:
        for index, line in enumerate(stream, 1):
            if not line.strip():
                raise ValueError("Empty edge at line " + str(index))
            edge = [int(value) for value in line.strip().split(",")]
            if len(set(edge)) != len(edge):
                raise ValueError("Repeated vertex within edge at line " + str(index))
            edges += 1
            incidences += len(edge)
            maximum_edge = max(maximum_edge, len(edge))
            vertices.update(edge)
    if not vertices or min(vertices) < 1:
        raise ValueError("Drivers require nonempty input with positive vertex IDs")
    if not allow_sparse and (min(vertices) != 1 or max(vertices) != len(vertices)):
        raise ValueError("Sparse IDs require explicit --allow-sparse after data auditing")
    return {"vertices": len(vertices), "edges": edges, "incidences": incidences,
            "max_edge_size": maximum_edge, "max_vertex_id": max(vertices),
            "dense_vertex_ids": min(vertices) == 1 and max(vertices) == len(vertices), "sha256": digest(path), "bytes": path.stat().st_size}


def parse_author_phases(log):
    """Preserve each author's clock and measurement boundaries explicitly."""
    baseline = [line.split(" ", 1)[1] for line in log.splitlines()
                if line.startswith("VLDB_CPU_PHASES ")]
    if baseline:
        if len(baseline) != 1:
            raise ValueError("Ambiguous baseline phase metrics")
        phases = json.loads(baseline[0])
        init, execution = phases["init_cpu_s"], phases["iteration_cpu_s"]
        clock = "CPU clock()"
    else:
        values = [re.findall(name + r":\s*([0-9.eE+-]+)\s*s", log)
                  for name in ["init_Time", "exc_Time"]]
        if any(len(value) != 1 for value in values):
            raise ValueError("Expected exactly one pair of SIGMOD phase metrics")
        init, execution = (float(value[0]) for value in values)
        clock = "wall high_resolution_clock"
    if init < 0 or execution < 0:
        raise ValueError("Negative author phase timing")
    return {"reported_init_s": init, "reported_execution_s": execution,
            "reported_total_s": init + execution, "reported_clock": clock}


def invoke(method, data, directory, name, cpu, timeout, memory_gib, export=False):
    core_path = directory / (name + ".cores.csv")
    time_path = directory / (name + ".time.txt")
    log_path = directory / (name + ".log")
    command = ["/usr/bin/time", "-v", "-o", str(time_path),
               "taskset", "-c", str(cpu), str(ROOT / "build/drivers" / method["binary"]),
               str(data), method["argument"], str(core_path) if export else "-"]
    environment = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", LC_ALL="C")
    def memory_limit():
        size = memory_gib * 1024 ** 3
        resource.setrlimit(resource.RLIMIT_AS, (size, size))
    started = time.monotonic()
    with log_path.open("w") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   env=environment, start_new_session=True, preexec_fn=memory_limit)
        try:
            code = process.wait(timeout=timeout)
            status = "ok" if code == 0 else "nonzero_exit"
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            code = process.wait()
            status = "timeout"
    row = {"method": method["id"], "run": name, "status": status, "exit_code": code,
           "process_wall_s": time.monotonic() - started, "command": command,
           "exported_cores": export}
    if status == "ok":
        text = log_path.read_text()
        values = [line.split(" ", 1)[1] for line in text.splitlines()
                  if line.startswith("REPRO_METRICS ")]
        if len(values) != 1:
            raise RuntimeError("Missing or ambiguous metrics in " + str(log_path))
        row.update(json.loads(values[0]))
        row.update(parse_author_phases(text))
        match = re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", time_path.read_text())
        if not match:
            raise RuntimeError("Missing peak RSS in " + str(time_path))
        row["peak_rss_kib"] = int(match.group(1))
        if export:
            row["core_sha256"] = digest(core_path)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-sparse", action="store_true")
    parser.add_argument("--profile", choices=["pilot", "paper"], default="pilot")
    parser.add_argument("--repetitions", type=int)
    parser.add_argument("--cpu", type=int, default=min(os.sched_getaffinity(0)))
    parser.add_argument("--timeout", type=int)
    parser.add_argument("--memory-gib", type=int, default=32)
    parser.add_argument("--seed", type=int, default=5012)
    args = parser.parse_args()
    if args.repetitions is None:
        args.repetitions = 3 if args.profile == "paper" else 5
    if args.timeout is None:
        args.timeout = 21600 if args.profile == "paper" else 900
    if args.repetitions < 1 or args.timeout < 1 or args.memory_gib < 1:
        parser.error("Repetitions, timeout and memory limit must be positive")
    if args.cpu not in os.sched_getaffinity(0):
        parser.error("Requested CPU is outside allowed affinity")
    args.input = args.input.resolve()
    args.output = args.output.resolve()
    if not args.output.is_relative_to(ROOT / "results"):
        parser.error("Output must be under the project's results directory")
    methods = json.loads((ROOT / "configs/methods.json").read_text())
    stats = input_stats(args.input, allow_sparse=args.allow_sparse)
    args.output.mkdir(parents=True, exist_ok=False)
    metadata = {"recorded_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "input": str(args.input), "data": stats, "methods": methods,
                "profile": args.profile, "primary_aggregate": "mean" if args.profile == "paper" else "median",
                "timing_note": "Reported total = author init + iteration timers; CPU/wall clock labeled separately. Driver wall timings retained.",
                "paper_profile_sha256": digest(ROOT / "configs/paper-profile.json") if args.profile == "paper" else None,
                "repetitions": args.repetitions, "cpu": args.cpu, "seed": args.seed,
                "timeout_s": args.timeout, "memory_limit_gib": args.memory_gib,
                "load_average_start": os.getloadavg(), "threads": 1,
                "binary_sha256": {m["binary"]: digest(ROOT / "build/drivers" / m["binary"])
                                  for m in methods}}
    (args.output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    warmups = []
    for method in methods:
        row = invoke(method, args.input, args.output, "validation_" + method["id"],
                     args.cpu, args.timeout, args.memory_gib, export=True)
        warmups.append(row)
        (args.output / "validation.json").write_text(json.dumps(warmups, indent=2) + "\n")
        if row["status"] != "ok" or row["vertices"] != stats["vertices"]:
            raise RuntimeError("Full-data validation failed: " + method["id"])
        if row["core_sha256"] != warmups[0]["core_sha256"]:
            raise RuntimeError("Core outputs disagree: " + method["id"])
        print("Validated " + method["id"], flush=True)
    schedule = [(repeat, method) for repeat in range(1, args.repetitions + 1) for method in methods]
    random.Random(args.seed).shuffle(schedule)
    rows = []
    with (args.output / "runs.jsonl").open("w") as journal:
        for repeat, method in schedule:
            name = "repeat_%02d_%s" % (repeat, method["id"])
            row = invoke(method, args.input, args.output, name,
                         args.cpu, args.timeout, args.memory_gib)
            row["repeat"] = repeat
            rows.append(row)
            journal.write(json.dumps(row) + "\n")
            journal.flush()
            print(name + ": " + row["status"], flush=True)
    summaries = []
    for method in methods:
        successful = [r for r in rows if r["method"] == method["id"] and r["status"] == "ok"]
        item = {"method": method["id"], "label": method["label"], "successful_runs": len(successful)}
        for metric in ["load_wall_s", "setup_wall_s", "compute_wall_s",
                       "total_before_export_wall_s", "process_wall_s", "peak_rss_kib",
                       "reported_init_s", "reported_execution_s", "reported_total_s"]:
            values = [r[metric] for r in successful]
            if values:
                item[metric] = {"median": statistics.median(values), "mean": statistics.mean(values),
                                "min": min(values), "max": max(values)}
        summaries.append(item)
    result = {"data": stats, "repetitions": args.repetitions, "cpu": args.cpu,
              "full_core_outputs_equal": True, "core_sha256": warmups[0]["core_sha256"],
              "profile": args.profile, "primary_aggregate": "mean" if args.profile == "paper" else "median",
              "methods": summaries, "load_average_end": os.getloadavg()}
    (args.output / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return int(any(row["status"] != "ok" for row in rows))


if __name__ == "__main__":
    raise SystemExit(main())
