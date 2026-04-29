#!/usr/bin/env bash
# scripts/run_tests.sh
# Build (if needed) and run the full test suite.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Ensure the extension is compiled
if ! python -c "from xhtml._core import RustDocument" 2>/dev/null; then
    echo "==> Extension not found — running dev install first..."
    bash "$SCRIPT_DIR/dev_install.sh"
fi

echo "==> Installing test dependencies..."
pip install pytest --quiet

echo "==> Running xhtml test suite..."
python -m pytest tests/ "$@"
