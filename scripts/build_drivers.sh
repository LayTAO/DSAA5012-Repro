#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p build/drivers results/setup
CXX="${CXX:-g++}"
FLAGS=(-O3 -DNDEBUG -std=c++20 -fopenmp -fstack-protector-strong)
{
  "$CXX" --version
  printf 'Common compiler flags:'
  printf ' %q' "${FLAGS[@]}"
  printf '\n'
  set -x
  "$CXX" "${FLAGS[@]}" -Iexternal/hyper-k-core/src \
    src/drivers/sigmod.cpp external/hyper-k-core/src/Hypergraph.cpp \
    external/hyper-k-core/src/Algorithm/*.cpp -o build/drivers/sigmod
  "$CXX" "${FLAGS[@]}" -Iexternal/vldbsubmission/cpp_src \
    src/drivers/vldb.cpp external/vldbsubmission/cpp_src/hypergraph.cpp \
    external/vldbsubmission/cpp_src/algorithms.cpp -o build/drivers/vldb
  set +x
  sha256sum build/drivers/sigmod build/drivers/vldb
} 2>&1 | tee results/setup/drivers-build.log
