#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" == 0 ]]; then
  echo 'Usage: bash scripts/run_on_server.sh COMMAND [ARGUMENTS...]' >&2
  exit 2
fi
REPRO_PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
source "${REPRO_PROJECT_ROOT}/scripts/server_env.sh"
cd "${REPRO_PROJECT_ROOT}"
exec "$@"
