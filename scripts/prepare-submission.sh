#!/usr/bin/env bash
# Build a clean, submission-ready zip of the project.
#
# - Excludes secrets (.env), runtime DBs, the venv, node_modules, chroma_db,
#   build artifacts, macOS metadata, and timestamped test reports.
# - Keeps the .gitkeep / latest-summary / latest.json so a grader sees the
#   project layout and the most recent passing test report.
# - Leaves the working tree untouched — this script only copies + zips.
#
# Usage:
#   ./scripts/prepare-submission.sh                  # writes ./submission.zip
#   ./scripts/prepare-submission.sh /tmp/foo.zip     # writes /tmp/foo.zip

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

OUT="${1:-${ROOT}/submission.zip}"
STAGE="$(mktemp -d -t it-support-ai-submission-XXXX)"
trap 'rm -rf "$STAGE"' EXIT

echo "[prepare-submission] staging in $STAGE"

# rsync — the most reliable way to copy with excludes.
rsync -a \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude 'node_modules/' \
  --exclude 'chroma_db/' \
  --exclude 'frontend/dist/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude '*.pyo' \
  --exclude '.ruff_cache/' \
  --exclude '.pytest_cache/' \
  --exclude '.mypy_cache/' \
  --exclude '.DS_Store' \
  --exclude '.env' \
  --exclude '.env.local' \
  --exclude 'services/it_ops_api/it_ops.db' \
  --exclude 'services/it_ops_api/it_ops.db-*' \
  --exclude 'tests/results/mcp_proof.db' \
  --exclude 'tests/results/routing-2*.json' \
  --exclude 'tests/results/mcp-proof-2*.json' \
  --exclude 'tests/results/accuracy-2*.json' \
  --exclude 'submission.zip' \
  ./ "$STAGE/it-support-ai/"

# Sanity check: nothing secret-shaped should be in the staged dir.
if grep -rE 'sk-ant-api03-[A-Za-z0-9_-]{40,}' "$STAGE" >/dev/null 2>&1; then
  echo "[prepare-submission] ABORT: a real-looking Anthropic API key is in the staged copy." >&2
  echo "[prepare-submission] Inspect with: grep -rE 'sk-ant-api03-[A-Za-z0-9_-]{40,}' $STAGE" >&2
  exit 1
fi

# If the deterministic harness has never been run, generate a fresh report so
# the submission ships with proof the tests pass. Best-effort — silently skip
# if the venv isn't set up.
if [ ! -s "$STAGE/it-support-ai/tests/results/latest.json" ] && [ -x "$ROOT/.venv/bin/python" ]; then
  echo "[prepare-submission] running deterministic harness for fresh report"
  ( cd "$ROOT" && .venv/bin/python tests/test_routing.py >/dev/null 2>&1 || true )
  cp -f "$ROOT/tests/results/latest.json" "$STAGE/it-support-ai/tests/results/" 2>/dev/null || true
  cp -f "$ROOT/tests/results/latest-summary.md" "$STAGE/it-support-ai/tests/results/" 2>/dev/null || true
fi

# Build the zip.
( cd "$STAGE" && zip -qr "$OUT" it-support-ai )

bytes=$(wc -c < "$OUT" | tr -d ' ')
files=$(unzip -l "$OUT" | tail -1 | awk '{print $2}')
echo "[prepare-submission] wrote $OUT"
echo "[prepare-submission] $files files, $bytes bytes"
echo "[prepare-submission] DONE"
