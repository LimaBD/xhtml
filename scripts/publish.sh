#!/usr/bin/env bash
# scripts/publish.sh
# Build wheels and publish to PyPI (or TestPyPI).
#
# Usage:
#   ./scripts/publish.sh            # publish to PyPI
#   ./scripts/publish.sh --test     # publish to TestPyPI
#
# Prerequisites:
#   export MATURIN_PYPI_TOKEN=pypi-xxxx   (for PyPI)
#   export MATURIN_PYPI_TOKEN=pypi-xxxx   (for TestPyPI)
#
# For multi-platform wheels (Linux x86_64, macOS, Windows), use the
# GitHub Actions publish workflow instead of this script.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

TEST_MODE=0
if [[ "${1:-}" == "--test" ]]; then
    TEST_MODE=1
fi

echo "==> Installing maturin..."
pip install "maturin>=1.5,<2.0" "twine" --quiet

echo "==> Running tests before publish..."
bash "$SCRIPT_DIR/run_tests.sh"

echo "==> Building release wheel..."
maturin build --release

WHEEL_DIR="$PROJECT_ROOT/.build/cargo/wheels"
echo "==> Wheel(s) built:"
ls -lh "$WHEEL_DIR"

if [[ $TEST_MODE -eq 1 ]]; then
    echo "==> Uploading to TestPyPI..."
    python -m twine upload \
        --repository-url https://test.pypi.org/legacy/ \
        "$WHEEL_DIR"/*.whl
    echo ""
    echo "✓ Published to TestPyPI."
    echo "  Test with: pip install -i https://test.pypi.org/simple/ xhtml"
else
    echo "==> Uploading to PyPI..."
    python -m twine upload "$WHEEL_DIR"/*.whl
    echo ""
    echo "✓ Published to PyPI."
    echo "  Install with: pip install xhtml"
fi
