#!/usr/bin/env bash
set -uo pipefail

export PAGER=cat
export GIT_PAGER=cat
export GH_PAGER=cat

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECTS_DIR="$(cd "${ROOT_DIR}/.." && pwd)"
TOPOLOGY_PY="${ROOT_DIR}/.venv/bin/python"

DRY_RUN=0
ALL_REPOS=0
PYTEST_ARGS=()

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --all-repos)
      ALL_REPOS=1
      shift
      ;;
    *)
      PYTEST_ARGS+=("$1")
      shift
      ;;
  esac
done

if [ "${ALL_REPOS}" -eq 1 ]; then
  REPOS=("sandbox-init" "abstract-ops" "interview-ops" "hostel-ops")
else
  REPOS=("sandbox-init")
fi

OVERALL_EXIT=0

for repo_name in "${REPOS[@]}"; do
  target_repo="${PROJECTS_DIR}/${repo_name}"
  if [ ! -d "${target_repo}" ]; then
    echo "WARN: skipping missing repository ${repo_name}" >&2
    continue
  fi

  (
    cd "${target_repo}" || exit 1
    if [ -f "${target_repo}/.env" ]; then
      set -a
      # shellcheck disable=SC1090
      source "${target_repo}/.env"
      set +a
    fi

    eval "$(
      PYTHONPATH="${ROOT_DIR}/src" "${TOPOLOGY_PY}" \
        -m sandbox_init.topology --format env --repo-root "${target_repo}"
    )"

    task_slug="cr024_integration_${repo_name//-/_}"
    if [ "${DRY_RUN}" -eq 1 ]; then
      echo "=== DRY-RUN TOPOLOGY (${repo_name}) ==="
      echo "CLUSTER_TOPOLOGY=${CLUSTER_TOPOLOGY}"
      echo "OLLAMA_URL=${OLLAMA_URL}"
      echo "CLUSTER_PG_HOST=${CLUSTER_PG_HOST}:${CLUSTER_PG_PORT}"
      echo "POSTGRES_DSN=${POSTGRES_DSN}"
      echo "HOSTEL_PG_DSN=${HOSTEL_PG_DSN}"
      echo "AUDIT_DB_PATH=${AUDIT_DB_PATH}"
      echo "CMD: ./scripts/run_logged.sh ${task_slug} -- .venv/bin/pytest -v -m integration ${PYTEST_ARGS[*]:-}"
      exit 0
    fi

    mkdir -p "${target_repo}/data"
    ./scripts/run_logged.sh "${task_slug}" -- \
      .venv/bin/pytest -v -m integration "${PYTEST_ARGS[@]}" 2>&1 | tail -n 15
    exit "${PIPESTATUS[0]}"
  )
  repo_exit=$?
  if [ "${repo_exit}" -ne 0 ]; then
    OVERALL_EXIT="${repo_exit}"
  fi
done

exit "${OVERALL_EXIT}"
