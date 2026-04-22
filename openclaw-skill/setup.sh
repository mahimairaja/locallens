#!/usr/bin/env bash
set -euo pipefail

# Check if locallens is installed
if ! command -v locallens &> /dev/null; then
    echo "Installing LocalLens..."
    pip install locallens
fi

echo "LocalLens $(locallens --version 2>/dev/null || echo installed) is ready."
locallens doctor
