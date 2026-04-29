#!/usr/bin/env bash
# scripts/run_benchmarks.sh
# Run the benchmark suite comparing xhtml to beautifulsoup4.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Ensure the extension is compiled
if ! python -c "from xhtml._core import RustDocument" 2>/dev/null; then
    echo "==> Extension not found — running dev install first..."
    bash "$SCRIPT_DIR/dev_install.sh"
fi

echo "==> Installing benchmark dependencies..."
pip install beautifulsoup4 --quiet

ITERS="${1:-100}"
echo "==> Running benchmarks (${ITERS} iterations per operation)..."
python tests/benchmark.py --iterations "$ITERS"
