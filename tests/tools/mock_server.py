"""Deterministic mock tool endpoints for tool-use tests.

All responses are fixed and reproducible. No external dependencies.

Run standalone: uvicorn tests.tools.mock_server:app --port 8765
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Mock Tool Server", version="1.0")


# --- Weather Tool ---

class WeatherRequest(BaseModel):
    city: str
    days: int = 5

WEATHER_DATA = {
    "London": {
        "city": "London",
        "country": "UK",
        "forecast": [
            {"day": 1, "high_c": 15, "low_c": 8, "condition": "Partly cloudy", "rain_pct": 30},
            {"day": 2, "high_c": 17, "low_c": 9, "condition": "Sunny", "rain_pct": 10},
            {"day": 3, "high_c": 14, "low_c": 7, "condition": "Rain", "rain_pct": 80},
            {"day": 4, "high_c": 13, "low_c": 6, "condition": "Overcast", "rain_pct": 50},
            {"day": 5, "high_c": 16, "low_c": 8, "condition": "Partly cloudy", "rain_pct": 25},
        ],
    },
    "Tokyo": {
        "city": "Tokyo",
        "country": "Japan",
        "forecast": [
            {"day": 1, "high_c": 22, "low_c": 15, "condition": "Sunny", "rain_pct": 5},
            {"day": 2, "high_c": 24, "low_c": 16, "condition": "Sunny", "rain_pct": 10},
            {"day": 3, "high_c": 20, "low_c": 14, "condition": "Cloudy", "rain_pct": 40},
            {"day": 4, "high_c": 19, "low_c": 13, "condition": "Rain", "rain_pct": 70},
            {"day": 5, "high_c": 21, "low_c": 15, "condition": "Partly cloudy", "rain_pct": 20},
        ],
    },
}

@app.post("/weather/forecast")
def get_forecast(req: WeatherRequest):
    data = WEATHER_DATA.get(req.city)
    if not data:
        raise HTTPException(404, f"City not found: {req.city}")
    result = data.copy()
    result["forecast"] = result["forecast"][:req.days]
    return result


# --- Search Tool ---

class SearchRequest(BaseModel):
    query: str
    max_results: int = 5

SEARCH_DATA = {
    "AI cost reduction": [
        {"title": "Reducing AI Inference Costs with Model Routing", "url": "https://example.com/1", "snippet": "Organizations can reduce AI costs by 60-80% through intelligent model routing, directing simple queries to smaller models."},
        {"title": "Local LLMs vs Cloud APIs: A Cost Analysis", "url": "https://example.com/2", "snippet": "Running local models on Apple Silicon achieves near-zero marginal inference cost at the expense of latency and quality ceiling."},
        {"title": "MAKER: Solving Complex Tasks with Cheap Models", "url": "https://example.com/3", "snippet": "Task decomposition with multi-agent voting enables cheap models to match expensive frontier performance."},
    ],
    "platform engineering": [
        {"title": "Platform Engineering in 2026", "url": "https://example.com/4", "snippet": "Internal developer platforms reduce cognitive load and accelerate delivery by abstracting infrastructure complexity."},
        {"title": "The Rise of AI-Powered Platform Teams", "url": "https://example.com/5", "snippet": "Platform teams are integrating AI assistants to automate toil, but cost governance remains an unsolved challenge."},
    ],
}

@app.post("/search")
def search(req: SearchRequest):
    # Return results for the closest matching query
    for key, results in SEARCH_DATA.items():
        if key.lower() in req.query.lower():
            return {"query": req.query, "results": results[:req.max_results]}
    return {"query": req.query, "results": []}


# --- File Read Tool ---

class FileReadRequest(BaseModel):
    path: str

FILE_DATA = {
    "src/calculator.py": '''\
"""Simple calculator module."""

def add(a: float, b: float) -> float:
    return a + b

def subtract(a: float, b: float) -> float:
    return a - b

def multiply(a: float, b: float) -> float:
    return a * b

def divide(a: float, b: float) -> float:
    return a / b  # BUG: no zero division check

def power(a: float, b: float) -> float:
    return a ** b
''',
    "tests/test_calculator.py": '''\
"""Tests for calculator module."""
import pytest
from src.calculator import add, subtract, multiply, divide, power

def test_add():
    assert add(2, 3) == 5

def test_subtract():
    assert subtract(5, 3) == 2

def test_multiply():
    assert multiply(4, 3) == 12

def test_divide():
    assert divide(10, 2) == 5.0

def test_divide_by_zero():
    with pytest.raises(ValueError):
        divide(10, 0)

def test_power():
    assert power(2, 3) == 8
''',
}

@app.post("/file/read")
def read_file(req: FileReadRequest):
    content = FILE_DATA.get(req.path)
    if content is None:
        raise HTTPException(404, f"File not found: {req.path}")
    return {"path": req.path, "content": content}


# --- Test Runner Tool ---

class RunTestsRequest(BaseModel):
    path: str

@app.post("/tests/run")
def run_tests(req: RunTestsRequest):
    # Deterministic: always return this specific failure
    return {
        "path": req.path,
        "passed": 5,
        "failed": 1,
        "errors": 0,
        "output": (
            "PASSED test_add\n"
            "PASSED test_subtract\n"
            "PASSED test_multiply\n"
            "PASSED test_divide\n"
            "FAILED test_divide_by_zero - ZeroDivisionError: division by zero\n"
            "  Expected: ValueError to be raised\n"
            "  Got: ZeroDivisionError: division by zero\n"
            "PASSED test_power\n"
            "\n5 passed, 1 failed"
        ),
    }
