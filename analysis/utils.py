"""Shared utilities for analysis scripts."""

import json
from pathlib import Path

from harness.paths import RAW_RESULTS_DIR, SCORED_RESULTS_DIR


def load_raw_results() -> list[dict]:
    """Load all raw JSON results."""
    results = []
    for path in sorted(RAW_RESULTS_DIR.glob("*.json")):
        with open(path) as f:
            results.append(json.load(f))
    return results


def load_scored_results() -> list[dict]:
    """Load all scored JSON results."""
    results = []
    for path in sorted(SCORED_RESULTS_DIR.glob("*.json")):
        with open(path) as f:
            results.append(json.load(f))
    return results
