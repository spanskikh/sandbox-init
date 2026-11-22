#!/usr/bin/env bash
set -uo pipefail

if [ $# -lt 3 ] || [ "$2" != "--" ]; then
  echo "Usage: $0 <task_name> -- <command...>" >&2
  exit 2
fi

TASK_NAME="$1"
shift 2

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${ROOT_DIR}/logs"
mkdir -p "${LOG_DIR}"

STAMP="$(date +%Y%m%d-%H%M%S)"
PREFIX="${LOG_DIR}/${STAMP}_${TASK_NAME}"
OUT_FILE="${PREFIX}.stdout"
ERR_FILE="${PREFIX}.stderr"
ALL_FILE="${PREFIX}.log"

START_ISO="$(date -Iseconds)"
START_EPOCH="$(date +%s)"

{
  echo "=== RUN START: ${START_ISO} | TASK: ${TASK_NAME} ==="
  echo "CMD: $*"
} | tee -a "${ALL_FILE}"

set +e
"$@" \
  > >(tee -a "${OUT_FILE}" "${ALL_FILE}") \
  2> >(tee -a "${ERR_FILE}" "${ALL_FILE}" >&2)
EXIT_CODE=$?
set -e

# Allow process substitution tee buffers to flush cleanly
sleep 0.05

END_ISO="$(date -Iseconds)"
END_EPOCH="$(date +%s)"
DURATION="$((END_EPOCH - START_EPOCH))"

{
  echo "=== RUN END: ${END_ISO} | DURATION: ${DURATION}s | EXIT_CODE: ${EXIT_CODE} ==="
  echo "ARTIFACTS: ${OUT_FILE} | ${ERR_FILE} | ${ALL_FILE}"
} | tee -a "${ALL_FILE}"

exit "${EXIT_CODE}"
