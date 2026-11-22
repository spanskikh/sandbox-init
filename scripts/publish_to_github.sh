#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -f docs/ci/ci.yml ]]; then
  echo "ERROR: docs/ci/ci.yml not found" >&2
  exit 1
fi

uv sync --extra dev
.venv/bin/ruff check src tests
.venv/bin/mypy src tests --strict
.venv/bin/pytest -v -m "not integration"

mkdir -p .github/workflows
git mv docs/ci/ci.yml .github/workflows/ci.yml
rmdir docs/ci 2>/dev/null || true

git add .github/workflows/ci.yml
git commit -m "ci: activate GitHub Actions verification and CycloneDX SBOM pipeline"

echo "Ready to publish. Run:"
echo "  gh repo edit --visibility public --accept-visibility-change-consequences && git push origin main"
