#!/usr/bin/env bash
# The six configurations and five in-process repeats from upstream main_run.sh.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
OUT="results/history-author-${1:-001}"
DATA="data/processed/history-author/history.hyp_sorted_by_edge_desc_node_asc.txt"
CPU="${CPU:-0}"
[[ ! -e "$OUT" ]] || { echo "Output already exists: $OUT" >&2; exit 1; }
mkdir "$OUT"
for algorithm in 0 1 2 3 4 5; do
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 LC_ALL=C \
  /usr/bin/time -v -o "$OUT/algorithm_${algorithm}.time.txt" \
    taskset -c "$CPU" build/native/HypergraphKCore "$DATA" "$algorithm" 5 \
    > "$OUT/algorithm_${algorithm}.log" 2>&1
  echo "Author CLI algorithm $algorithm: completed"
done
