#!/usr/bin/env bash
# scripts/build.sh
# Build release wheels for the current platform.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "==> Building release wheel..."
cd "$PROJECT_ROOT"

pip install "maturin>=1.5,<2.0" --quiet
maturin build --release

echo ""
echo "✓ Wheel(s) built successfully."
ls -lh "$PROJECT_ROOT/.build/cargo/wheels/"
