#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
test "${TMPDIR:-}" = "$ROOT/.runtime/tmp"
mkdir -p build/extended/generated results/setup
python3 - <<'PY'
from pathlib import Path
import hashlib,json
p=Path('external/hyper-k-core/src/graphTool/graphTool.cpp');s=p.read_text()
if s.count('std::random_device rd;')!=2:raise RuntimeError('Unexpected source')
s=s.replace('#include "graphTool.h"','#include "graphTool/graphTool.h"')
s='#include <cstdint>\nextern std::uint32_t repro_seed;\n'+s.replace('std::random_device rd;','auto rd=[](){return repro_seed;};')
out=Path('build/extended/generated/seeded_graph_tools.cpp');out.write_text(s)
Path('results/setup/sampling-adaptations.json').write_text(json.dumps({'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'generated_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'change':'Explicit RNG seed only; original vary_edges selection, including its EOF behavior, retained.'},indent=2)+'\n')
PY
g++ -O3 -DNDEBUG -std=c++20 -fopenmp -fstack-protector-strong \
  -Iexternal/hyper-k-core/src src/drivers/sample_sizes.cpp \
  build/extended/generated/seeded_graph_tools.cpp external/hyper-k-core/src/Hypergraph.cpp \
  external/hyper-k-core/src/graphTool/sortGraph.cpp -o build/extended/sample_sizes
g++ -O3 -DNDEBUG -std=c++20 -fstack-protector-strong src/drivers/audit_hypergraph.cpp -o build/extended/audit_hypergraph
sha256sum build/extended/sample_sizes build/extended/audit_hypergraph
