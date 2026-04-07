"""Evaluator modules for the local LLM benchmark.

Each evaluator scores model outputs on category-specific sub-dimensions,
returning a dict of percentage scores (0.0-100.0).

Modules:
    code_correctness  — code generation: correctness, completeness, quality, style
    lint_scorer        — ruff + pylint quality scoring (used by code_correctness)
    bug_detection      — code review: precision, recall, false positives
    summary_coverage   — summarisation: key-point coverage, concision
    hallucination_check — claim-level hallucination detection
    tool_format        — tool-use: format compliance, task completion, efficiency
    llm_judge          — Claude Sonnet structured judge for subjective axes
"""
