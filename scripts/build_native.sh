#!/usr/bin/env bash
# Compile the upstream CLI directly; no CMake installation or source patch required.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p build/native results/setup
CXX="${CXX:-g++}"
{
  "$CXX" --version
  set -x
  "$CXX" -O3 -DNDEBUG -std=c++20 -fopenmp -fstack-protector-strong \
    external/hyper-k-core/src/main.cpp external/hyper-k-core/src/Hypergraph.cpp \
    external/hyper-k-core/src/Algorithm/*.cpp \
    external/hyper-k-core/src/Algorithm_withInfo/*.cpp \
    external/hyper-k-core/src/graphTool/*.cpp -o build/native/HypergraphKCore
  set +x
  sha256sum build/native/HypergraphKCore
} 2>&1 | tee results/setup/native-build.log
