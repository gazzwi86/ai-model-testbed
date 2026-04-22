"""
Calculator Module
Provides basic arithmetic operations and an expression evaluator.
"""

import re


class Calculator:
    """A simple calculator with memory and history support."""

    def __init__(self):
        self.memory = 0.0
        self.history = []

    def add(self, a, b):
        """Return the sum of a and b."""
        result = a + b
        self._record("add", a, b, result)
        return result

    def subtract(self, a, b):
        """Return a minus b."""
        result = a - b
        self._record("subtract", a, b, result)
        return result

    def multiply(self, a, b):
        """Return the product of a and b."""
        result = a * b
        self._record("multiply", a, b, result)
        return result

    def divide(self, a, b):
        """Return a divided by b.

        BUG: Division by zero is not handled. When b is 0, this raises
        an unhandled ZeroDivisionError instead of returning a meaningful
        error or raising a custom exception.
        """
        result = a / b  # raises ZeroDivisionError when b == 0
        self._record("divide", a, b, result)
        return result

    def power(self, base, exponent):
        """Return base raised to the exponent."""
        result = base ** exponent
        self._record("power", base, exponent, result)
        return result

    def modulo(self, a, b):
        """Return a modulo b."""
        # Also affected by the same division-by-zero issue
        result = a % b
        self._record("modulo", a, b, result)
        return result

    def store_memory(self, value):
        """Store a value in memory."""
        self.memory = value

    def recall_memory(self):
        """Recall the stored memory value."""
        return self.memory

    def clear_memory(self):
        """Clear the stored memory value."""
        self.memory = 0.0

    def get_history(self):
        """Return the full operation history."""
        return list(self.history)

    def clear_history(self):
        """Clear the operation history."""
        self.history.clear()

    def _record(self, operation, a, b, result):
        """Record an operation in the history."""
        self.history.append({
            "operation": operation,
            "operands": [a, b],
            "result": result,
        })

    def evaluate(self, expression):
        """Evaluate a simple arithmetic expression string.

        Supports +, -, *, / with integer and float operands.
        Does NOT support parentheses or operator precedence beyond
        left-to-right evaluation.

        Examples:
            evaluate("3 + 4")      -> 7.0
            evaluate("10 / 2 + 3") -> 8.0  (left to right)
            evaluate("6 / 0")      -> ZeroDivisionError (BUG)
        """
        # Tokenise: split into numbers and operators
        tokens = re.findall(r"[\d.]+|[+\-*/]", expression)
        if not tokens:
            raise ValueError(f"Invalid expression: {expression!r}")

        result = float(tokens[0])
        i = 1
        while i < len(tokens):
            op = tokens[i]
            operand = float(tokens[i + 1])
            if op == "+":
                result = self.add(result, operand)
            elif op == "-":
                result = self.subtract(result, operand)
            elif op == "*":
                result = self.multiply(result, operand)
            elif op == "/":
                result = self.divide(result, operand)  # BUG: no zero check
            else:
                raise ValueError(f"Unknown operator: {op!r}")
            i += 2

        return result
