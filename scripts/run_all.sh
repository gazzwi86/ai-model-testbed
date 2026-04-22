#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

source .venv/bin/activate

echo "=== Running Full Benchmark Suite ==="
echo "Start: $(date)"

# Standard benchmark (all categories, all models, all tiers)
python -m harness.runner "$@"

# MDAP benchmark
echo ""
echo "=== Running MDAP Tests ==="
python -m harness.runner --mdap-only

# Score results
echo ""
echo "=== Scoring Results ==="
python -m analysis.score_results

# Generate cost report
echo ""
echo "=== Computing Costs ==="
python -m analysis.cost_calculator

# Generate tables and charts
echo ""
echo "=== Generating Outputs ==="
python -m analysis.generate_tables
python -m analysis.generate_charts

echo ""
echo "=== Complete ==="
echo "End: $(date)"
echo "Results in: $PROJECT_DIR/results/"
