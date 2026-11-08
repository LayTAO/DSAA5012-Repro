#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
test "${TMPDIR:-}" = "$ROOT/.runtime/tmp"
mkdir -p build/extended results/setup
python3 scripts/generate_extended_sources.py
INFO=()
for source in external/hyper-k-core/src/Algorithm_withInfo/*.cpp; do
  if [[ "$(basename "$source")" != fullNbrCoreDecomposition.cpp ]]; then INFO+=("$source"); fi
done
g++ -O3 -DNDEBUG -std=c++20 -fopenmp -fstack-protector-strong \
  -Iexternal/hyper-k-core/src -Isrc/drivers src/drivers/sigmod_extended.cpp \
  external/hyper-k-core/src/Hypergraph.cpp external/hyper-k-core/src/Algorithm/*.cpp \
  "${INFO[@]}" build/extended/generated/suc_counters.cpp -o build/extended/sigmod_extended
g++ -O3 -DNDEBUG -std=c++20 -fopenmp -fstack-protector-strong \
  -Iexternal/hyper-k-core/src src/drivers/generate_synthetic.cpp \
  build/extended/generated/seeded_generator.cpp -o build/extended/generate_synthetic
sha256sum build/extended/sigmod_extended build/extended/generate_synthetic
