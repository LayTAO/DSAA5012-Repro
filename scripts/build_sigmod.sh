#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="${PROJECT_ROOT}/external/hyper-k-core"
BUILD_DIR="${PROJECT_ROOT}/build/sigmod2025"

if ! command -v cmake >/dev/null 2>&1; then
  echo "CMake is required. Install it before building." >&2
  exit 1
fi
if [[ ! -f "${SOURCE_DIR}/CMakeLists.txt" ]]; then
  echo "Run python3 scripts/fetch_upstream.py first." >&2
  exit 1
fi

cmake -S "${SOURCE_DIR}" -B "${BUILD_DIR}" -DCMAKE_BUILD_TYPE=Release
cmake --build "${BUILD_DIR}" --parallel "${BUILD_JOBS:-4}"
