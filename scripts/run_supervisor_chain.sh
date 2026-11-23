#!/usr/bin/env bash
set -uo pipefail

export PAGER=cat
export GIT_PAGER=cat
export GH_PAGER=cat

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECTS_DIR="$(cd "${ROOT_DIR}/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"

DRY_RUN=0
ORCH_ARGS=()

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    *)
      ORCH_ARGS+=("$1")
      shift
      ;;
  esac
done

if [ "${#ORCH_ARGS[@]}" -eq 0 ]; then
  ORCH_ARGS=("--scenario" "all" "--format" "summary")
fi

if [ "${DRY_RUN}" -eq 1 ]; then
  echo "=== DRY-RUN SUPERVISOR CHAIN (CR-025) ==="
  echo "PROJECTS_DIR=${PROJECTS_DIR}"
  echo "CHAIN=sandbox-init -> abstract-ops -> interview-ops -> hostel-ops"
  echo "CMD: ./scripts/run_logged.sh cr025_supervisor_chain -- .venv/bin/python -m sandbox_init.orchestrator ${ORCH_ARGS[*]}"
  exit 0
fi

cd "${ROOT_DIR}" || exit 1
PYTHONPATH="${ROOT_DIR}/src" ./scripts/run_logged.sh cr025_supervisor_chain -- \
  "${PYTHON_BIN}" -m sandbox_init.orchestrator "${ORCH_ARGS[@]}" 2>&1 | tail -n 15
exit "${PIPESTATUS[0]}"
