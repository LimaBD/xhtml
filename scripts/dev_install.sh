#!/usr/bin/env bash
# scripts/dev_install.sh
# Install xhtml in editable/development mode.
# The Rust extension is compiled and placed into xhtml/ automatically.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "==> Checking prerequisites..."
command -v cargo >/dev/null 2>&1 || { echo "ERROR: cargo not found. Install Rust: https://rustup.rs"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found."; exit 1; }

echo "==> Installing maturin (if not present)..."
pip install "maturin>=1.5,<2.0" --quiet

echo "==> Building Rust extension and installing xhtml in dev mode..."
cd "$PROJECT_ROOT"
maturin develop --release

echo ""
echo "✓ xhtml installed in development mode."
echo "  Try: python -c \"from xhtml import Xhtml; print('OK')\""
