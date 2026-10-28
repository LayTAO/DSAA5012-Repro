#!/usr/bin/env python3
"""Export only bounded, small summaries; never transfer data or vertex-level cores."""
import json
from pathlib import Path
import re
import statistics
from benchmark import ROOT


def stats(values):
    return {"mean": statistics.mean(values), "median": statistics.median(values),
            "min": min(values), "max": max(values)}


def text(path):
    if path.stat().st_size > 131072:
        raise ValueError("Refusing to export a file larger than 128 KiB: " + str(path))
    return path.read_text().replace(str(ROOT), "${PROJECT_ROOT}")


def main():
    pilot = ROOT / "results/history-pilot-001"
    package = {}
    for name in ["summary.json", "metadata.json", "runs.jsonl", "validation.json"]:
        package[name] = text(pilot / name)
    package["correctness.json"] = text(ROOT / "results/correctness-001/summary.json")
    package["data-manifest.json"] = text(ROOT / "data/processed/history-author/manifest.json")
    package["environment.json"] = text(ROOT / "results/setup/environment.json")
    for name in ["drivers-build.log", "native-build.log"]:
        package[name] = text(ROOT / "results/setup" / name)
    phases = []
    for line in (pilot / "runs.jsonl").read_text().splitlines():
        row = json.loads(line)
        log = (pilot / (row["run"] + ".log")).read_text()
        phase = {"method": row["method"], "repeat": row["repeat"]}
        if row["method"].startswith("sigmod"):
            phase["clock"] = "upstream high_resolution_clock wall time"
            for key, pattern in [("init_s", "init_Time"), ("iteration_s", "exc_Time")]:
                values = re.findall(pattern + r":\s*([0-9.eE+-]+)\s*s", log)
                if len(values) != 1:
                    raise ValueError("Expected one upstream phase time: " + row["run"])
                phase[key] = float(values[0])
        else:
            phase["clock"] = "upstream clock() CPU time"
            values = [json.loads(value.split(" ", 1)[1]) for value in log.splitlines()
                      if value.startswith("VLDB_CPU_PHASES ")]
            if len(values) != 1:
                raise ValueError("Expected one baseline CPU phase record")
            phase.update(values[0])
        phases.append(phase)
    package["phase-timings.json"] = json.dumps(phases, indent=2) + "\n"
    author = []
    for algorithm in range(6):
        folder = ROOT / "results/history-author-001"
        log = (folder / ("algorithm_%d.log" % algorithm)).read_text()
        item = {"algorithm": algorithm, "repeats_in_one_process": 5,
                "clock": "upstream high_resolution_clock wall time"}
        for key, pattern in [("init_s", "init_Time"), ("iteration_s", "exc_Time")]:
            values = [float(value) for value in re.findall(pattern + r":\s*([0-9.eE+-]+)\s*s", log)]
            if len(values) != 5:
                raise ValueError("Expected five author CLI phase measurements")
            item[key] = {"values": values, **stats(values)}
        usage = (folder / ("algorithm_%d.time.txt" % algorithm)).read_text()
        item["peak_rss_kib"] = int(re.search(r"Maximum resident set size \(kbytes\):\s*(\d+)", usage).group(1))
        author.append(item)
    package["author-cli.json"] = json.dumps(author, indent=2) + "\n"
    payload = json.dumps(package)
    if len(payload.encode()) > 262144:
        raise ValueError("Summary package exceeds 256 KiB")
    print(payload)


if __name__ == "__main__":
    main()
