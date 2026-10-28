#!/usr/bin/env python3
"""Preserve the bundled input and apply the author's org + sortEV preprocessing."""
import json
from pathlib import Path
import shutil
import subprocess
from benchmark import ROOT, digest, input_stats


def main():
    source = ROOT / "external/hyper-k-core/datasets/coauth-MAG-History-full.hyp"
    raw = ROOT / "data/raw/history-bundled/coauth-MAG-History-full.hyp"
    processed = ROOT / "data/processed/history-author"
    if processed.exists():
        raise RuntimeError("Processed directory already exists; refusing to overwrite")
    source_hash = digest(source)
    raw.parent.mkdir(parents=True, exist_ok=True)
    if raw.exists():
        if digest(raw) != source_hash:
            raise RuntimeError("Existing raw data differs from pinned upstream source")
    else:
        shutil.copyfile(source, raw)
    processed.mkdir()
    working = processed / "history.hyp"
    shutil.copyfile(raw, working)
    binary = ROOT / "build/native/HypergraphKCore"
    commands = [[str(binary), str(working), "org"],
                [str(binary), str(working), "sortEV", "desc", "asc"]]
    with (processed / "preprocessing.log").open("w") as log:
        for command in commands:
            subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT,
                           timeout=900)
    output = Path(str(working) + "_sorted_by_edge_desc_node_asc.txt")
    metadata = {"source": "https://github.com/unswdb/hyper-k-core",
                "source_commit": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=source.parents[1], text=True).strip(),
                "source_file": "datasets/coauth-MAG-History-full.hyp",
                "raw_sha256": source_hash, "raw_bytes": raw.stat().st_size,
                "commands": commands, "processed": input_stats(output),
                "note": "Author org deduplicates members within each edge and drops edges of size <2; sortEV reorders vertices and edges. Duplicate hyperedges remain."}
    if digest(raw) != source_hash or digest(source) != source_hash:
        raise RuntimeError("Raw input integrity check failed")
    (processed / "manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
