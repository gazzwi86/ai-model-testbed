"""
Tests for the Calculator module.

Several tests in this file FAIL because of unhandled division by zero in
calculator.py. The model's task is to read the test output, diagnose the
root cause, and propose a fix.
"""

import pytest
import sys
import os

# Add src to path so we can import calculator
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from calculator import Calculator


@pytest.fixture
def calc():
    return Calculator()


# ── Basic arithmetic (these pass) ──────────────────────────────────

class TestBasicArithmetic:
    def test_add(self, calc):
        assert calc.add(2, 3) == 5

    def test_add_negative(self, calc):
        assert calc.add(-1, -1) == -2

    def test_add_floats(self, calc):
        assert calc.add(0.1, 0.2) == pytest.approx(0.3)

    def test_subtract(self, calc):
        assert calc.subtract(10, 4) == 6

    def test_subtract_negative_result(self, calc):
        assert calc.subtract(3, 7) == -4

    def test_multiply(self, calc):
        assert calc.multiply(3, 4) == 12

    def test_multiply_by_zero(self, calc):
        assert calc.multiply(5, 0) == 0

    def test_divide(self, calc):
        assert calc.divide(10, 2) == 5.0

    def test_divide_float_result(self, calc):
        assert calc.divide(7, 2) == 3.5

    def test_power(self, calc):
        assert calc.power(2, 10) == 1024

    def test_power_zero_exponent(self, calc):
        assert calc.power(5, 0) == 1

    def test_modulo(self, calc):
        assert calc.modulo(10, 3) == 1


# ── Division by zero (these FAIL) ─────────────────────────────────

class TestDivisionByZero:
    """These tests document the expected behaviour for division by zero.
    They currently FAIL because calculator.py does not handle this case."""

    def test_divide_by_zero_raises_value_error(self, calc):
        """Division by zero should raise ValueError, not ZeroDivisionError."""
        with pytest.raises(ValueError, match="Cannot divide by zero"):
            calc.divide(10, 0)

    def test_modulo_by_zero_raises_value_error(self, calc):
        """Modulo by zero should raise ValueError, not ZeroDivisionError."""
        with pytest.raises(ValueError, match="Cannot divide by zero"):
            calc.modulo(10, 0)

    def test_evaluate_division_by_zero(self, calc):
        """Evaluating '6 / 0' should raise ValueError."""
        with pytest.raises(ValueError, match="Cannot divide by zero"):
            calc.evaluate("6 / 0")


# ── Memory (these pass) ───────────────────────────────────────────

class TestMemory:
    def test_initial_memory_is_zero(self, calc):
        assert calc.recall_memory() == 0.0

    def test_store_and_recall(self, calc):
        calc.store_memory(42)
        assert calc.recall_memory() == 42

    def test_clear_memory(self, calc):
        calc.store_memory(99)
        calc.clear_memory()
        assert calc.recall_memory() == 0.0


# ── History (these pass) ──────────────────────────────────────────

class TestHistory:
    def test_history_initially_empty(self, calc):
        assert calc.get_history() == []

    def test_operations_recorded(self, calc):
        calc.add(1, 2)
        calc.multiply(3, 4)
        history = calc.get_history()
        assert len(history) == 2
        assert history[0]["operation"] == "add"
        assert history[1]["operation"] == "multiply"

    def test_clear_history(self, calc):
        calc.add(1, 2)
        calc.clear_history()
        assert calc.get_history() == []


# ── Expression evaluator ──────────────────────────────────────────

class TestEvaluate:
    def test_simple_addition(self, calc):
        assert calc.evaluate("3 + 4") == 7.0

    def test_simple_subtraction(self, calc):
        assert calc.evaluate("10 - 3") == 7.0

    def test_chained_operations(self, calc):
        # Left-to-right: (10 / 2) + 3 = 8.0
        assert calc.evaluate("10 / 2 + 3") == 8.0

    def test_empty_expression_raises(self, calc):
        with pytest.raises(ValueError):
            calc.evaluate("")

    def test_invalid_expression_raises(self, calc):
        with pytest.raises(ValueError):
            calc.evaluate("hello world")
