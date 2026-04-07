"""Centralised path constants for the project."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
PROMPTS_DIR = PROJECT_ROOT / "tests" / "prompts"
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
RESULTS_DIR = PROJECT_ROOT / "results"
RAW_RESULTS_DIR = RESULTS_DIR / "raw"
SCORED_RESULTS_DIR = RESULTS_DIR / "scored"
CHARTS_DIR = RESULTS_DIR / "charts"
