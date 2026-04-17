#!/usr/bin/env bash
set -euo pipefail

echo "=== LocalLens Install Test ==="

TMPDIR=$(mktemp -d)
trap 'rm -rf -- "$TMPDIR"' EXIT

echo "1. Creating fresh venv..."
python3 -m venv "$TMPDIR/venv"
source "$TMPDIR/venv/bin/activate"

echo "2. Installing locallens (base)..."
pip install -e "." --quiet

echo "3. Testing Python API import..."
python -c "from locallens import LocalLens, __version__; print(f'LocalLens v{__version__} imported OK')"

echo "4. Testing CLI..."
locallens --help > /dev/null && echo "locallens --help: OK"

echo "5. Testing doctor (checks may fail without services)..."
locallens doctor --format json 2>/dev/null \
  | python -c "import sys, json; d=json.load(sys.stdin); print(f'Doctor: {len(d[\"checks\"])} checks')" \
  || echo "Doctor: ran (some checks failed as expected)"

echo "6. Installing MCP extra..."
pip install -e ".[mcp]" --quiet

echo "7. Testing serve --help..."
locallens serve --help > /dev/null && echo "locallens serve --help: OK"

echo ""
echo "=== All install tests passed ==="
