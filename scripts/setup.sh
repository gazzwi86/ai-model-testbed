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

# 2. Check Python
PYTHON_VERSION=$(python3 --version 2>&1)
echo "Python: $PYTHON_VERSION"

# 3. Create venv if needed
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$PROJECT_DIR/.venv"
fi

source "$PROJECT_DIR/.venv/bin/activate"
echo "Installing dependencies..."
pip install -r "$PROJECT_DIR/requirements.txt" --quiet

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
    "mistral:7b"
)

for model in "${MODELS[@]}"; do
    echo "Pulling $model..."
    ollama pull "$model"
done

echo ""
echo "=== Setup complete ==="
echo "Run: python -m harness.runner --model gemma4:e4b --category code_gen --tier simple"
