#!/bin/bash
set -euo pipefail

echo "=== Local LLM Benchmark Setup ==="

# 1. Check Ollama
if ! command -v ollama &> /dev/null; then
    echo "ERROR: Ollama not found. Install from https://ollama.com"
    exit 1
fi

OLLAMA_VERSION=$(ollama --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
echo "Ollama version: $OLLAMA_VERSION"

# 2. Check uv
if ! command -v uv &> /dev/null; then
    echo "ERROR: uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "uv version: $(uv --version)"

# 3. Create venv with pinned Python and install deps
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo "Creating virtual environment (Python 3.12)..."
    uv venv --python 3.12 "$PROJECT_DIR/.venv"
fi

source "$PROJECT_DIR/.venv/bin/activate"
echo "Installing dependencies..."
uv pip install -e "$PROJECT_DIR"

# 4. Check ANTHROPIC_API_KEY
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo "WARNING: ANTHROPIC_API_KEY not set. Frontier model tests will fail."
fi

# 5. Pull models
echo ""
echo "=== Pulling models (~70GB total) ==="
echo "This will take a while on first run..."

MODELS=(
    "gemma4:e4b"
    "gemma4:26b"
    "gemma4:31b"
    "qwen3.5:9b"
    "qwen3.5:27b"
    "deepseek-r1:14b"
    "deepseek-coder:6.7b"
    "mistral-small3.2"
)

for model in "${MODELS[@]}"; do
    echo "Pulling $model..."
    ollama pull "$model"
done

echo ""
echo "=== Setup complete ==="
echo "Run: python -m harness.runner --model gemma4:e4b --category code_gen --tier simple"
