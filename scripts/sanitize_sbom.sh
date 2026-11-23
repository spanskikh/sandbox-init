#!/usr/bin/env bash
set -uo pipefail

export PAGER=cat
export GIT_PAGER=cat
export GH_PAGER=cat

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECTS_DIR="$(cd "${ROOT_DIR}/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"

DRY_RUN=0
ALL_REPOS=0
SBOM_ARGS=()

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
      SBOM_ARGS+=("$1")
      shift
      ;;
  esac
done

if [ "${ALL_REPOS}" -eq 1 ]; then
  REPOS=("sandbox-init" "abstract-ops" "interview-ops" "hostel-ops")
else
  REPOS=("sandbox-init")
fi

if [ "${DRY_RUN}" -eq 1 ]; then
  echo "=== DRY-RUN SBOM SANITIZER (CR-026) ==="
  echo "PROJECTS_DIR=${PROJECTS_DIR}"
  echo "REPOS=${REPOS[*]}"
  if [ "${#SBOM_ARGS[@]}" -eq 0 ]; then
    echo "CMD: ./scripts/run_logged.sh cr026_sanitize_sbom -- .venv/bin/python -m sandbox_init.sbom --generate --output ${PROJECTS_DIR}/tmp/sandbox-init.sbom.cdx.json --verify --format summary"
  else
    echo "CMD: ./scripts/run_logged.sh cr026_sanitize_sbom -- .venv/bin/python -m sandbox_init.sbom ${SBOM_ARGS[*]}"
  fi
  exit 0
fi

mkdir -p "${PROJECTS_DIR}/tmp"

if [ "${ALL_REPOS}" -eq 1 ] && [ "${#SBOM_ARGS[@]}" -eq 0 ]; then
  OVERALL_EXIT=0
  for repo_name in "${REPOS[@]}"; do
    target_repo="${PROJECTS_DIR}/${repo_name}"
    if [ ! -d "${target_repo}" ]; then
      echo "WARN: skipping missing repository ${repo_name}" >&2
      continue
    fi
    out_file="${PROJECTS_DIR}/tmp/${repo_name}.sbom.cdx.json"
    task_slug="cr026_sbom_${repo_name//-/_}"
    (
      cd "${ROOT_DIR}" || exit 1
      PYTHONPATH="${ROOT_DIR}/src" ./scripts/run_logged.sh "${task_slug}" -- \
        "${PYTHON_BIN}" -m sandbox_init.sbom \
        --generate \
        --repo-root "${target_repo}" \
        --output "${out_file}" \
        --verify \
        --format summary 2>&1 | tail -n 15
      exit "${PIPESTATUS[0]}"
    )
    repo_exit=$?
    if [ "${repo_exit}" -ne 0 ]; then
      OVERALL_EXIT="${repo_exit}"
    fi
  done
  exit "${OVERALL_EXIT}"
fi

if [ "${#SBOM_ARGS[@]}" -eq 0 ]; then
  SBOM_ARGS=(
    "--generate"
    "--output"
    "${PROJECTS_DIR}/tmp/sandbox-init.sbom.cdx.json"
    "--verify"
    "--format"
    "summary"
  )
fi

cd "${ROOT_DIR}" || exit 1
PYTHONPATH="${ROOT_DIR}/src" ./scripts/run_logged.sh cr026_sanitize_sbom -- \
  "${PYTHON_BIN}" -m sandbox_init.sbom "${SBOM_ARGS[@]}" 2>&1 | tail -n 15
exit "${PIPESTATUS[0]}"
