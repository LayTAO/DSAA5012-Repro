#!/usr/bin/env bash
# Source this before any server download, build, or experiment.
# All managed files stay in the current user's home on a non-root filesystem.

repro_setup_server_environment() {
  local repro_project repro_home repro_root_device repro_home_device repro_project_device
  if [[ "$(uname -s)" != Linux ]]; then
    echo "This environment guard is for the Linux experiment server." >&2
    return 1
  fi
  if [[ "$(id -u)" == 0 ]]; then
    echo "Run as the ordinary experiment user, not root." >&2
    return 1
  fi
  repro_home="$(realpath -e -- "${HOME:?HOME is required}")" || return 1
  repro_project="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)" || return 1
  case "${repro_project}" in
    "${repro_home}/"*) ;;
    *) echo "Project must be inside the experiment user's home." >&2; return 1 ;;
  esac
  repro_root_device="$(stat -c %d /)" || return 1
  repro_home_device="$(stat -c %d "${repro_home}")" || return 1
  repro_project_device="$(stat -c %d "${repro_project}")" || return 1
  if [[ "${repro_home_device}" == "${repro_root_device}" || "${repro_project_device}" != "${repro_home_device}" ]]; then
    echo "Refusing to write: home/project must share a filesystem distinct from /." >&2
    return 1
  fi

  # Validate all managed destinations before creating anything. Resolve existing
  # symlinks as well, so a cache or build link cannot redirect writes onto /.
  local relative resolved existing
  for relative in .runtime .runtime/tmp .runtime/cache .runtime/config .runtime/data .runtime/state .runtime/cache/pip .runtime/cache/ccache .runtime/cache/python .venv external data data/raw data/processed build results; do
    resolved="$(realpath -m -- "${repro_project}/${relative}")" || return 1
    case "${resolved}" in
      "${repro_project}/"*) ;;
      *) echo "Refusing redirected path: ${relative}" >&2; return 1 ;;
    esac
    existing="${resolved}"
    while [[ ! -e "${existing}" ]]; do existing="$(dirname "${existing}")"; done
    if [[ "$(stat -c %d "${existing}")" != "${repro_home_device}" ]]; then
      echo "Refusing destination on another filesystem: ${relative}" >&2
      return 1
    fi
  done

  mkdir -p "${repro_project}/.runtime/tmp" "${repro_project}/.runtime/cache/pip" \
    "${repro_project}/.runtime/cache/ccache" "${repro_project}/.runtime/config" \
    "${repro_project}/.runtime/data" "${repro_project}/.runtime/state" || return 1
  export TMPDIR="${repro_project}/.runtime/tmp"
  export TMP="${TMPDIR}" TEMP="${TMPDIR}"
  export XDG_CACHE_HOME="${repro_project}/.runtime/cache"
  export XDG_CONFIG_HOME="${repro_project}/.runtime/config"
  export XDG_DATA_HOME="${repro_project}/.runtime/data"
  export XDG_STATE_HOME="${repro_project}/.runtime/state"
  export PIP_CACHE_DIR="${XDG_CACHE_HOME}/pip"
  export CCACHE_DIR="${XDG_CACHE_HOME}/ccache"
  export PYTHONPYCACHEPREFIX="${XDG_CACHE_HOME}/python"
  export CMAKE_BUILD_PARALLEL_LEVEL="${BUILD_JOBS:-4}"
  ulimit -c 0 || return 1
  printf 'Experiment root: %s\nTemporary files: %s\n' "${repro_project}" "${TMPDIR}" >&2
}

if repro_setup_server_environment; then
  unset -f repro_setup_server_environment
else
  unset -f repro_setup_server_environment
  return 1 2>/dev/null || exit 1
fi
