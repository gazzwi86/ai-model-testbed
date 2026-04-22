# Local LLM Cost Reduction: Test Plan & Implementation Guide

> **Purpose:** This document is the implementation plan for Claude Code. It contains sufficient detail to build the full test harness, run benchmarks, and produce results for a blog post on AI cost reduction through local/hybrid model routing.
>
> **Central thesis:** Running AI on a local machine and routing requests between local, self-hosted, and frontier models delivers sizeable cost reductions — especially when combined with MAKER-style multi-agent decomposition and voting.
>
> **Reference paper:** Meyerson et al., "Solving a Million-Step LLM Task with Zero Errors" (arXiv:2511.09030, Nov 2025) — the MAKER system demonstrates that extreme task decomposition + multi-agent voting with cheap models can match expensive frontier model quality.

---

## 1. Hardware Context

### MacBook Pro M4 24GB

| Spec | Value | Implication |
|---|---|---|
| Unified memory | 24GB | Shared CPU/GPU — no separate VRAM. OS + Ollama overhead ~4-5GB, leaving ~19GB for model + KV cache |
| Memory bandwidth | ~120 GB/s | This is the throughput bottleneck, not compute. Directly determines tok/s |
| Inference runtime | Ollama 0.19+ (MLX backend) | MLX activates automatically on Apple Silicon. ~1.6x faster prefill, ~2x faster decode vs pre-MLX |
| Practical model ceiling | ~14B dense, or MoE up to ~35B total (≤4B active) at Q4 | Larger models work but with severely limited context windows |
| Context pressure | At 14B Q4 (~9GB model): ~10GB left for KV cache = 8-16K context. At 20GB model: ~4GB left = 2-4K context | Must set `num_ctx` deliberately per model |

### Key caveat for the article

Ollama 0.19's MLX preview officially recommends 32GB+. On 24GB you will hit memory pressure with larger models at long context. This is itself a compelling data point — it shows where the hardware boundary bites and strengthens the argument for intelligent routing.

---

## 2. Model Selection Matrix

All models available via `ollama pull`. Grouped by role.

### Local Models Under Test

| # | Model | Params | Active | Size (Q4) | Context (safe on 24GB) | Role | Rationale |
|---|---|---|---|---|---|---|---|
| L1 | **Gemma 4 E4B** | 4B | 4B | ~3GB | 16K+ | Lightweight general | Apr 2026, multimodal, PLE arch, 128K native. Fast and cheap — the MAKER microagent candidate |
| L2 | **Gemma 4 26B-A4B** | 26B MoE | 3.8B | ~15GB | 8-16K | Flagship MoE | Only 3.8B active — 8B-class speed, near-30B quality. Best quality-per-watt on this hardware |
| L3 | **Gemma 4 31B** | 31B dense | 31B | ~18-20GB | 2-4K | Max local quality | #3 open model on Arena AI. Q4 fits in 24GB but context severely limited. Tests the "best possible local quality at short context" boundary |
| L4 | **Qwen 3.5 9B** | 9B | 9B | ~6.6GB | 16K+ | Strong mid-range | Hybrid thinking mode, 256K native, excellent code + reasoning. Good MAKER microagent candidate |
| L5 | **Qwen 2.5 Coder 14B** | 14B | 14B | ~9GB | 8K | Coding specialist | Purpose-built for code gen/completion. Tests whether task-specific models beat generalists |
| L6 | **DeepSeek-R1-Distill-14B** | 14B | 14B | ~9GB | 8K | Reasoning specialist | CoT reasoning distilled from R1. Tests reasoning depth at local scale |
| L7 | **Mistral Small 3** | 7B | 7B | ~5GB | 16K+ | Fast general | Strong instruction-following, good speed. Baseline "fast and light" option |

### Frontier Baselines (Claude API)

| Model | Input/MTok | Output/MTok | Role in Test |
|---|---|---|---|
| **Haiku 4.5** | $1.00 | $5.00 | Floor: "Can local match this cheapest frontier tier?" |
| **Sonnet 4.6** | $3.00 | $15.00 | Mid: "When must you pay for balanced frontier quality?" |
| **Opus 4.6** | $5.00 | $25.00 | Ceiling: "Is this ever necessary vs local + Sonnet routing?" |

### Ollama Pull Commands

```bash
# Claude Code: run these in sequence. Wait for each to complete before the next.
ollama pull gemma4:e4b
ollama pull gemma4:26b-a4b
ollama pull gemma4:31b
ollama pull qwen3.5:9b
ollama pull qwen2.5-coder:14b
ollama pull deepseek-r1:14b
ollama pull mistral-small3
```

---

## 3. Test Categories & Task Design

Each category has 3 tiers: **simple** (local should suffice), **medium** (boundary zone), **hard** (frontier likely wins). This structure directly tests the "quality tiers" thesis.

### 3.1 Code Generation & Completion

| Tier | Task | Inputs | What It Tests |
|---|---|---|---|
| Simple | Generate a Python function to parse a CSV file and compute column averages, with type hints and docstring | Prompt only | Basic code gen, stdlib knowledge, convention adherence |
| Medium | Build a FastAPI endpoint with JWT auth middleware, structured error handling, Pydantic models, and auto-generated OpenAPI docs | Prompt + requirements spec (YAML) | Multi-file reasoning, framework knowledge, production patterns |
| Hard | Implement a concurrent task scheduler with backpressure, configurable retry with exponential backoff, circuit breaker pattern, and structured logging/observability hooks | Prompt + interface definition | Architecture, edge cases, production-grade design |

**Evaluation criteria (scored 1-5 each):**
- **Functional correctness:** Does it run? Does it produce correct output? (Automated: execute + assert)
- **Code quality:** Passes ruff/pylint with no errors? (Automated: linting score)
- **Completeness:** Handles edge cases? Type hints? Docstrings? Error handling? (Checklist, partially automated)
- **Idiomatic style:** Follows language/framework conventions? (Human review)

**Claude Code implementation notes:**
- Store prompts in `tests/prompts/code_gen/simple.yaml`, `medium.yaml`, `hard.yaml`
- For functional correctness: generate the code to a temp file, run it with pytest assertions
- For linting: run `ruff check` and `pylint` on generated code, parse scores
- Each YAML prompt file should include: `prompt`, `expected_outputs` (for assertion), `evaluation_type`, `planted_test_cases`

### 3.2 Code Review & Refactoring

| Tier | Task | Inputs | What It Tests |
|---|---|---|---|
| Simple | Review a 50-line Python script with 3 planted bugs: off-by-one in a loop, unclosed file handle, silent type coercion error | Script + prompt | Bug detection precision and recall |
| Medium | Review a 200-line module with: God class (>5 responsibilities), missing input validation, SQL injection vulnerability, hardcoded credentials, no error handling on I/O | Module + prompt | Pattern recognition, security awareness, architectural smell detection |
| Hard | Refactor a tangled 500-line legacy module (circular imports, global state, mixed concerns) into clean components with preserved behaviour and explanation of changes | Module + prompt | Deep refactoring ability, maintaining behaviour, communication of rationale |

**Evaluation criteria:**
- **Bug detection:** Precision (correct bugs found / total bugs reported) and recall (correct bugs found / total planted bugs). Automated via checklist matching.
- **False positive rate:** Bugs reported that aren't real. Lower is better.
- **Explanation quality:** Does the review explain *why* something is a bug, not just *that* it is? (Human review, 1-5)
- **Refactoring fidelity:** Does refactored code pass the same test suite as original? (Automated)

**Claude Code implementation notes:**
- Pre-create the buggy scripts in `tests/fixtures/code_review/`
- Each fixture needs a `bugs.json` manifest listing: `{bug_id, description, line_range, severity, category}`
- Evaluation: parse model output for bug mentions, fuzzy-match against manifest
- For refactoring tier: include a `test_suite.py` that must pass before and after

### 3.3 Document Summarisation

| Tier | Task | Inputs | What It Tests |
|---|---|---|---|
| Simple | Summarise a 1-page meeting transcript into 3 bullet points capturing decisions, actions, and owners | 500-word transcript | Extraction, concision, structure |
| Medium | Summarise a 10-page technical architecture document, preserving: key decisions made, alternatives considered, trade-offs accepted, and open risks | ~4,000-word doc | Comprehension, fidelity to source, hierarchical summarisation |
| Hard | Summarise a 30-page RFP response identifying: compliance gaps, risk areas, pricing anomalies, and missing deliverables | ~12,000-word doc | Long-context reasoning, domain knowledge, analytical depth |

**Evaluation criteria:**
- **Key point coverage:** Percentage of key points captured (from a human-authored gold-standard checklist). Automated: embed both summaries + gold standard, compute cosine similarity per point.
- **Factual accuracy:** Number of claims that contradict the source. Manual spot-check + automated extraction.
- **Hallucination count:** Claims present in summary but absent from source. Critical metric.
- **Concision ratio:** Summary length / source length. Lower is better (within coverage threshold).

**Claude Code implementation notes:**
- Source documents go in `tests/fixtures/summarisation/`
- Gold standard key points go in `tests/fixtures/summarisation/gold/` as JSON arrays
- **Context length warning:** The hard tier (12K words = ~16K tokens) will exceed safe context for Gemma 4 31B and may stress 14B models. Record whether the model was able to process the full input. If truncated, note it — this is a valid test result showing local model limitations.

### 3.4 Writing & Content Drafting

| Tier | Task | Inputs | What It Tests |
|---|---|---|---|
| Simple | Write a 200-word internal Slack update about a project milestone (given: project name, milestone, date, next steps) | Structured brief | Tone, structure, concision, professional register |
| Medium | Draft a 1,000-word blog post on "Why platform engineering teams should care about AI cost governance" with examples and a clear argument structure | Topic brief + target audience | Argument structure, technical accuracy, voice, engagement |
| Hard | Create a 2,000-word thought leadership piece on a given technical topic with original analysis, counterarguments, a clear thesis, and a practical recommendation framework | Topic + audience + constraints | Depth, originality, persuasion, balanced argumentation |

**Evaluation criteria:**
- **Blind human review (1-5)** on: clarity, accuracy, engagement, originality, appropriate register
- Present all outputs anonymised and randomised to 2 human reviewers
- Record inter-rater agreement (Cohen's kappa)

**Claude Code implementation notes:**
- These cannot be fully automated. The harness should output all responses to `results/writing/` as individual markdown files, stripped of model identifiers, with a randomised filename mapping stored separately in `results/writing/_mapping.json`
- Include a simple scoring UI: a script that presents each output and collects 1-5 ratings via CLI input

### 3.5 Data Analysis & Transformation

| Tier | Task | Inputs | What It Tests |
|---|---|---|---|
| Simple | Given a JSON dataset (100 records, 5 fields), write a Python script to compute: mean, median, std dev per numeric column, and count of unique values per categorical column | JSON file + prompt | Data handling basics, stdlib usage |
| Medium | Clean a messy CSV: mixed date formats (DD/MM/YYYY, MM-DD-YYYY, ISO), missing values (empty, "N/A", "null", "-"), duplicate rows, inconsistent casing in categorical fields. Output normalised CSV. | Messy CSV + spec | Data wrangling, edge case handling, spec compliance |
| Hard | Analyse a multi-table dataset (3 CSVs with foreign keys), identify correlations between variables, and produce a narrative summary with statistical caveats and visualisation recommendations | 3 CSV files + analysis brief | Analytical reasoning, statistical literacy, communication |

**Evaluation criteria:**
- **Output correctness:** Does the generated script produce correct output when run against the test data? (Automated: run script, diff output against expected)
- **Edge case handling:** Does it handle the planted edge cases? (Automated: specific test assertions)
- **Narrative quality (hard tier only):** Accuracy of statistical claims, appropriate caveats (Human review)

**Claude Code implementation notes:**
- Generate test datasets programmatically in `tests/fixtures/data_analysis/generate_fixtures.py`
- Include expected outputs in `tests/fixtures/data_analysis/expected/`
- The messy CSV should have specific, documented edge cases so we can score handling

### 3.6 General Reasoning & Q&A

| Tier | Task | Inputs | What It Tests |
|---|---|---|---|
| Simple | "Explain the CAP theorem to a non-technical executive in 3 sentences" | Prompt only | Clarity, accuracy, audience calibration |
| Medium | "Compare event-driven and request-response architectures for a high-throughput IoT platform with 50K devices reporting every 10 seconds. Recommend one with trade-offs." | Prompt + constraints | Nuanced reasoning, balanced analysis, quantitative thinking |
| Hard | "A client wants to migrate from a monolith to microservices. They have 4 dev teams (avg 6 people), 2M daily active users, 200ms p99 latency SLA, and a 6-month deadline. The monolith is a 500K LOC Java app with a single Oracle DB. What's your recommendation and what are the top 3 ways it could fail?" | Prompt + detailed constraints | Multi-constraint reasoning, real-world judgment, risk identification |

**Evaluation criteria:**
- **Factual accuracy:** Are technical claims correct? (Expert review, checklist)
- **Nuance:** Does it acknowledge trade-offs, or give a one-sided answer? (1-5)
- **Actionability:** Could a tech lead act on this advice? (1-5)
- **Hallucination check:** Any fabricated facts, frameworks, or statistics? (Boolean per claim)

### 3.7 Tool Interaction & Agentic Tasks

| Tier | Task | Inputs | What It Tests |
|---|---|---|---|
| Simple | Given a weather API tool schema (OpenAPI spec), generate a correct function call to get the 5-day forecast for London | Tool schema JSON + prompt | Tool-use format compliance, schema adherence |
| Medium | Multi-step: (1) search for recent articles on a topic using a search tool, (2) extract key claims, (3) draft a summary response citing sources | Tool schemas + prompt | Planning, chaining, context management |
| Hard | Agentic loop: diagnose why a test suite is failing by (1) reading the test file, (2) reading the source file, (3) running the tests, (4) identifying the bug, (5) proposing a fix | Tool schemas + repo fixture | Autonomous reasoning, error recovery, multi-step tool orchestration |

**Evaluation criteria:**
- **Format compliance:** Does the tool call match the expected schema? (Automated: JSON schema validation)
- **Task completion rate:** Did the model complete the full task? (Binary + partial credit)
- **Attempts needed:** How many tool calls before success? (Lower is better)
- **Error recovery:** When a tool call fails, does the model adapt? (For hard tier only)

**Claude Code implementation notes:**
- Implement mock tool endpoints in `tests/tools/mock_server.py` using FastAPI
- Tools: `search(query) -> results[]`, `read_file(path) -> content`, `run_tests(path) -> output`, `weather(city) -> forecast`
- The mock server should return deterministic responses for reproducibility

---

## 4. MAKER-Inspired Multi-Agent Voting Test

### Background: The MAKER Paper

The MAKER system (Meyerson et al., arXiv:2511.09030, Nov 2025) from Cognizant AI Lab + UT Austin demonstrates three principles:

1. **Maximal Agentic Decomposition (MAD):** Break a task into the smallest possible subtasks, each handled by a focused microagent with minimal context. One subtask per agent. This limits context to the minimum needed, enabling use of smaller, cheaper models.

2. **First-to-ahead-by-k voting:** Run multiple independent microagents on each subtask. Accept the answer only when one candidate leads by k votes. This drives error rate exponentially toward zero. The maths: if per-step accuracy is p > 0.5, then with k-threshold voting the probability of the correct answer winning approaches 1 as k increases. Cost scales log-linearly with steps.

3. **Red-flagging:** Discard any response with structural indicators of failure (too long, malformed, off-topic) before it enters the voting pool. This cheaply filters out low-confidence outputs.

**The key cost insight:** The paper found that smaller, cheaper, non-reasoning models (e.g., GPT-4.1-mini) often provide the best reliability-per-dollar. The optimal model minimises `cost_per_token / per_step_accuracy`. The most expensive model is rarely the most cost-effective in a MAKER configuration.

**Our thesis extension:** If MAKER works with cloud API models, it should work even better with local models where the marginal cost per inference is near-zero (just electricity + hardware amortisation). The latency cost of running 5 parallel local inferences may still be faster than a single frontier API call (network RTT + queue time). This is the "local MDAP advantage."

### Test Design: MDAP Benchmark

We test MDAP (Massively Decomposed Agentic Process) across two task types to show generalisability beyond the paper's Towers of Hanoi domain.

#### Test 4.1: Code Generation via Decomposition + Voting

**Task:** Generate a complete Python module implementing a URL shortener service with: URL validation, Base62 encoding, SQLite storage, collision detection, and expiry handling.

**Approach A — Monolithic (baseline):**
Single prompt to each model. Score the output using standard code gen evaluation.

**Approach B — MDAP with voting:**

**Step 1: Decomposition** (performed once, by Claude Sonnet 4.6 or by Gemma 4 31B locally to test whether decomposition itself can be done locally):

Break the task into atomic subtasks with explicit interface contracts:

```yaml
subtasks:
  - id: validate_url
    prompt: "Write a function validate_url(url: str) -> bool that checks if a URL is valid using urllib.parse. Return True if the URL has a valid scheme (http/https) and netloc."
    inputs: null
    outputs: "validate_url function"
    tests:
      - "assert validate_url('https://example.com') == True"
      - "assert validate_url('not-a-url') == False"
      - "assert validate_url('ftp://example.com') == False"

  - id: encode_base62
    prompt: "Write a function encode_base62(number: int) -> str that converts a non-negative integer to a Base62 string (0-9, a-z, A-Z). encode_base62(0) should return '0'."
    inputs: null
    outputs: "encode_base62 function"
    tests:
      - "assert encode_base62(0) == '0'"
      - "assert encode_base62(61) == 'Z'"
      - "assert len(encode_base62(999999)) > 0"

  - id: storage
    prompt: "Write a class UrlStorage that wraps SQLite with methods: store(short_code: str, url: str, expires_at: datetime | None) -> None, lookup(short_code: str) -> str | None (returns None if expired or not found), delete_expired() -> int (returns count deleted). Use a table 'urls' with columns: short_code TEXT PRIMARY KEY, url TEXT NOT NULL, expires_at TEXT."
    inputs: null
    outputs: "UrlStorage class"
    tests:
      - "storage.store('abc', 'https://example.com', None); assert storage.lookup('abc') == 'https://example.com'"
      - "# expired URL returns None"

  - id: generate_short_code
    prompt: "Write a function generate_short_code(url: str, storage: UrlStorage) -> str that: (1) hashes the URL with hashlib.md5, (2) converts first 8 bytes to int, (3) encodes with encode_base62, (4) checks storage for collision, (5) if collision on different URL, increment and retry up to 10 times, (6) raises ValueError if all retries exhausted."
    inputs: "encode_base62, UrlStorage"
    outputs: "generate_short_code function"
    tests:
      - "# generates a non-empty string"
      - "# same URL produces same code"
      - "# different URLs produce different codes"

  - id: main_module
    prompt: "Write a main module that wires validate_url, encode_base62, UrlStorage, and generate_short_code into a CLI with argparse. Commands: 'shorten <url> [--expires-in-hours N]', 'resolve <short_code>', 'cleanup' (delete expired). Print results to stdout."
    inputs: "all prior subtasks"
    outputs: "main module with CLI"
    tests:
      - "# shorten a valid URL returns a code"
      - "# resolve a stored code returns the URL"
```

**Step 2: Microagent execution** (local models):

For each subtask, run N=k independent inferences using a cheap local model. The models to test as microagents:
- Gemma 4 E4B (fastest, cheapest — the MAKER-optimal candidate)
- Qwen 3.5 9B (stronger reasoning, still fast)
- Gemma 4 26B-A4B (best local quality, slower)

Each inference gets: the subtask prompt + interface contracts + accepted outputs from prior subtasks (if any dependencies).

**Step 3: Red-flag filtering:**

Before voting, discard outputs that:
- Fail `ast.parse()` (not valid Python)
- Exceed 2x expected length (likely hallucinating or repeating)
- Import disallowed modules (os.system, subprocess, etc.)
- Contain the subtask prompt echoed back (common failure mode)

Implementation:
```python
# tests/mdap/red_flag_filter.py
import ast

def red_flag_check(code: str, max_lines: int = None) -> tuple[bool, str]:
    """Returns (passed, reason). passed=True means output is acceptable."""
    # 1. Syntax check
    try:
        ast.parse(code)
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"

    # 2. Length check
    if max_lines and code.count('\n') > max_lines * 2:
        return False, f"Output too long: {code.count(chr(10))} lines vs {max_lines} expected"

    # 3. Disallowed imports
    disallowed = ['os.system', 'subprocess', 'eval(', 'exec(']
    for d in disallowed:
        if d in code:
            return False, f"Disallowed pattern: {d}"

    return True, "passed"
```

**Step 4: Voting:**

```python
# tests/mdap/voter.py

def functional_vote(candidates: list[str], test_assertions: list[str]) -> str | None:
    """Run each candidate's code against test assertions. Return first to pass all."""
    results = []
    for i, code in enumerate(candidates):
        passed = run_tests(code, test_assertions)
        results.append((i, passed, len([p for p in passed if p])))

    # Sort by number of passing tests (descending)
    results.sort(key=lambda x: x[2], reverse=True)

    # If top candidate passes all tests, accept it
    if results[0][2] == len(test_assertions):
        return candidates[results[0][0]]

    # Otherwise, return candidate with most passing tests
    # (with tie-break on shortest code)
    top_score = results[0][2]
    tied = [r for r in results if r[2] == top_score]
    tied.sort(key=lambda r: len(candidates[r[0]]))  # shortest first
    return candidates[tied[0][0]]
```

**Step 5: Assembly and integration test:**

Concatenate accepted subtask outputs into a single module. Run the full integration test suite. Score using identical criteria to Approach A.

#### Test 4.2: Document Analysis via Decomposition + Voting

**Task:** Analyse the same 10-page technical proposal from test 3.3 (medium tier) and produce: (1) executive summary, (2) risk register, (3) gap analysis against a requirements checklist.

**Approach A — Monolithic:** Single prompt with full document. (Note: exceeds context for Gemma 4 31B — valid finding.)

**Approach B — MDAP:**

1. **Decomposition:** Split document into sections by heading. Generate per-section subtasks:
   - Per section: "Summarise the key claims and decisions in 3 bullet points"
   - Per section: "Identify risks or gaps mentioned or implied"
   - Cross-section synthesis: "Given these section summaries, write a 200-word executive summary"
   - Cross-section synthesis: "Consolidate per-section risks into a risk register with likelihood/impact"
   - Cross-section synthesis: "Compare section summaries against this requirements checklist, identify gaps"

2. **Microagent execution:** Each section-level subtask run N=3 times by cheap local model

3. **Voting for text outputs:** Since text doesn't have binary test assertions, use embedding-based majority vote:
   ```python
   # Embed all N outputs for a subtask
   # Compute pairwise cosine similarity
   # Select the output closest to the centroid (most representative / "median" answer)
   from sentence_transformers import SentenceTransformer
   import numpy as np

   model = SentenceTransformer('all-MiniLM-L6-v2')

   def embedding_vote(candidates: list[str]) -> str:
       embeddings = model.encode(candidates)
       centroid = np.mean(embeddings, axis=0)
       similarities = [np.dot(e, centroid) / (np.linalg.norm(e) * np.linalg.norm(centroid))
                       for e in embeddings]
       return candidates[np.argmax(similarities)]
   ```

4. **Assembly:** Feed voted section outputs into cross-section synthesis subtasks.

**Critical measurement: Does MDAP allow a small model to handle a document that exceeds its context window?** If so, this is a major finding for the article — MDAP as a context-window workaround.

#### MDAP Implementation Architecture

```
tests/mdap/
├── decomposer.py          # Takes a task prompt, calls a planner model to produce subtasks
│                          # Input: task description string
│                          # Output: list of SubTask objects (prompt, deps, tests, max_lines)
│                          # Can use either Claude API or local model for decomposition
├── microagent.py           # Runs N inferences of a subtask against a local model via Ollama
│                          # Input: SubTask, model_id, k (number of runs), prior_outputs
│                          # Output: list of N response strings
│                          # Uses asyncio for parallel execution when no dependencies
├── red_flag_filter.py      # Filters outputs: syntax, length, format
│                          # Input: list of candidate outputs, filter config
│                          # Output: filtered list + discard log
├── voter.py                # Voting strategies
│                          # functional_vote: for code (run tests)
│                          # embedding_vote: for text (centroid selection)
│                          # hybrid_vote: try functional, fall back to embedding
├── assembler.py            # Concatenates accepted subtask outputs
│                          # Runs integration tests
│                          # Returns assembled output + integration test results
├── cost_tracker.py         # Tracks tokens consumed, wall time per subtask and total
│                          # Computes: local_cost, equivalent_frontier_cost, savings_ratio
├── runner.py               # Orchestrates: decompose -> execute -> filter -> vote -> assemble
│                          # Supports both code_gen and doc_analysis task types
└── tasks/
    ├── url_shortener/
    │   ├── task.yaml        # Full task description + monolithic prompt
    │   ├── subtasks.yaml    # Pre-decomposed subtasks (can also be generated dynamically)
    │   ├── contracts.yaml   # Interface contracts between subtasks
    │   ├── test_integration.py  # Full integration tests for assembled output
    │   └── subtask_tests/   # Per-subtask test assertions
    │       ├── test_validate_url.py
    │       ├── test_encode_base62.py
    │       ├── test_storage.py
    │       ├── test_generate_short_code.py
    │       └── test_main.py
    └── doc_analysis/
        ├── task.yaml
        ├── source_doc.md    # The 10-page proposal
        ├── requirements_checklist.yaml
        ├── gold_summary.md  # Human-authored gold standard
        └── gold_risks.yaml  # Human-authored risk register
```

---

## 5. Test Harness Architecture

### Directory Structure

```
local-llm-benchmark/
├── README.md
├── requirements.txt
├── config.yaml                     # Master config (see below)
├── tests/
│   ├── prompts/                    # YAML test definitions per category
│   │   ├── code_gen/
│   │   │   ├── simple.yaml
│   │   │   ├── medium.yaml
│   │   │   └── hard.yaml
│   │   ├── code_review/
│   │   ├── summarisation/
│   │   ├── writing/
│   │   ├── data_analysis/
│   │   ├── reasoning/
│   │   └── tool_use/
│   ├── fixtures/                   # Input data for tests
│   │   ├── code_review/            # Buggy scripts + bug manifests
│   │   ├── summarisation/          # Source docs + gold standards
│   │   ├── data_analysis/          # Test datasets + expected outputs
│   │   └── tool_use/               # Mock tool schemas + repo fixtures
│   ├── evaluators/                 # Automated scoring
│   │   ├── code_correctness.py
│   │   ├── lint_scorer.py
│   │   ├── bug_detection.py
│   │   ├── summary_coverage.py
│   │   ├── hallucination_check.py
│   │   └── tool_format.py
│   ├── mdap/                       # MAKER-inspired tests (Section 4)
│   │   └── (see Section 4 architecture)
│   └── tools/
│       └── mock_server.py          # FastAPI mock tool endpoints
├── harness/
│   ├── runner.py                   # Main orchestrator
│   ├── ollama_client.py            # Ollama native API wrapper
│   ├── claude_client.py            # Claude API wrapper
│   ├── metrics.py                  # Token/latency/cost capture
│   ├── model_lifecycle.py          # Load/unload models to manage 24GB memory
│   └── config_loader.py
├── results/
│   ├── raw/                        # JSON per run
│   └── scored/                     # JSON with evaluation scores
├── analysis/
│   ├── score_results.py
│   ├── cost_calculator.py
│   ├── generate_tables.py          # Markdown comparison tables
│   └── generate_charts.py          # Charts for article
└── scripts/
    ├── setup.sh
    ├── run_all.sh
    ├── run_category.sh
    └── run_mdap.sh
```

### config.yaml

```yaml
ollama:
  base_url: "http://localhost:11434"
  default_params:
    temperature: 0.3
    num_ctx: 8192

models:
  local:
    - id: "gemma4:e4b"
      name: "Gemma 4 E4B"
      num_ctx: 16384
      notes: "Lightweight, fast. Primary MDAP microagent candidate."
    - id: "gemma4:26b-a4b"
      name: "Gemma 4 26B A4B"
      num_ctx: 8192
      notes: "MoE flagship. 3.8B active. Best quality-per-watt."
    - id: "gemma4:31b"
      name: "Gemma 4 31B Dense"
      num_ctx: 4096
      notes: "Max quality, very tight memory. May swap. Test decomposition capability."
    - id: "qwen3.5:9b"
      name: "Qwen 3.5 9B"
      num_ctx: 16384
      notes: "Hybrid thinking. Good all-rounder and MDAP candidate."
    - id: "qwen2.5-coder:14b"
      name: "Qwen 2.5 Coder 14B"
      num_ctx: 8192
      notes: "Coding specialist."
    - id: "deepseek-r1:14b"
      name: "DeepSeek R1 Distill 14B"
      num_ctx: 8192
      notes: "Reasoning specialist. CoT."
    - id: "mistral-small3"
      name: "Mistral Small 3"
      num_ctx: 16384
      notes: "Fast, good instruction following."

  frontier:
    - id: "claude-haiku-4-5-20251001"
      name: "Claude Haiku 4.5"
      input_price_per_mtok: 1.00
      output_price_per_mtok: 5.00
    - id: "claude-sonnet-4-6"
      name: "Claude Sonnet 4.6"
      input_price_per_mtok: 3.00
      output_price_per_mtok: 15.00
    - id: "claude-opus-4-6"
      name: "Claude Opus 4.6"
      input_price_per_mtok: 5.00
      output_price_per_mtok: 25.00

test_params:
  runs_per_test: 3
  temperature_code: 0.3
  temperature_writing: 0.7
  mdap_k: 3                     # Default voting: 3 inferences per subtask
  mdap_k_sensitivity: 5         # Sensitivity test: 5 inferences

local_cost:
  power_watts: 30
  electricity_per_kwh_gbp: 0.30
  hardware_cost_gbp: 2499
  amortisation_years: 3
  # Derived: ~GBP0.10/hour = ~$0.13/hour
```

### Prompt YAML Format

```yaml
# tests/prompts/code_gen/simple.yaml
category: code_generation
tier: simple
name: "CSV column averages"
description: "Generate a Python function to parse CSV and compute column averages"

prompt: |
  Write a Python function called `compute_column_averages(filepath: str) -> dict[str, float]`
  that reads a CSV file and returns a dictionary mapping each numeric column name to its
  average value. Non-numeric columns should be skipped. The function should handle:
  - Empty files (return empty dict)
  - Files with headers but no data rows (return empty dict)
  - Mixed numeric/non-numeric columns
  Include type hints and a docstring.

temperature: 0.3
max_output_tokens: 1000

evaluation:
  type: "code_execution"
  test_file: "tests/fixtures/code_gen/test_csv_averages.py"
  lint: true
  checklist:
    - "Has type hints"
    - "Has docstring"
    - "Handles empty file"
    - "Handles non-numeric columns"
    - "Uses csv module or pandas"
```

### Model Lifecycle Management

```python
# harness/model_lifecycle.py
"""
Claude Code: Implement this to prevent OOM on 24GB.
Before loading a model >10GB, unload any currently loaded large model.
"""

import aiohttp

LARGE_MODEL_THRESHOLD_GB = 10

async def get_loaded_models(base_url: str) -> list[dict]:
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{base_url}/api/ps") as resp:
            data = await resp.json()
            return data.get('models', [])

async def unload_model(base_url: str, model_id: str):
    """Send a request with keep_alive=0 to unload."""
    async with aiohttp.ClientSession() as session:
        await session.post(f"{base_url}/api/chat", json={
            "model": model_id,
            "messages": [],
            "keep_alive": 0
        })

async def ensure_capacity(base_url: str, target_model: dict, all_models: list[dict]):
    """Unload large models if target model is large and memory is constrained."""
    target_size_gb = target_model.get('size_gb', 0)
    if target_size_gb < LARGE_MODEL_THRESHOLD_GB:
        return

    loaded = await get_loaded_models(base_url)
    for m in loaded:
        if m['name'] != target_model['id']:
            await unload_model(base_url, m['name'])
            # Wait for unload
            import asyncio
            await asyncio.sleep(2)
```

### Runner Core Logic (Pseudocode)

```python
# harness/runner.py
"""
Usage:
  python harness/runner.py                          # Run all
  python harness/runner.py --category code_gen       # One category
  python harness/runner.py --model gemma4:e4b        # One model
  python harness/runner.py --tier simple             # One tier
  python harness/runner.py --mdap-only               # MDAP tests only
"""

async def run_single_test(model, prompt, run_idx, backend, config):
    """Execute one test, capture response + all metrics."""
    start = time.time()

    if backend == 'ollama':
        # Use native Ollama API for detailed metrics
        response = await ollama_chat(
            model=model['id'],
            messages=[{"role": "user", "content": prompt['prompt']}],
            temperature=prompt.get('temperature', config['ollama']['default_params']['temperature']),
            num_ctx=model.get('num_ctx', config['ollama']['default_params']['num_ctx']),
            base_url=config['ollama']['base_url']
        )
        metrics = {
            'prompt_tokens': response.get('prompt_eval_count', 0),
            'completion_tokens': response.get('eval_count', 0),
            'ttft_ms': response.get('prompt_eval_duration', 0) / 1e6,
            'total_duration_ms': response.get('total_duration', 0) / 1e6,
            'tokens_per_second': (
                response['eval_count'] / (response['eval_duration'] / 1e9)
                if response.get('eval_duration', 0) > 0 else 0
            ),
            'cost_usd': compute_local_cost(response.get('total_duration', 0), config),
        }
        response_text = response['message']['content']
    else:
        # Claude API
        response = await claude_chat(model['id'], prompt['prompt'],
                                      prompt.get('temperature', 0.3),
                                      prompt.get('max_output_tokens', 2000))
        metrics = {
            'prompt_tokens': response.usage.input_tokens,
            'completion_tokens': response.usage.output_tokens,
            'total_duration_ms': (time.time() - start) * 1000,
            'cost_usd': compute_claude_cost(response.usage, model),
        }
        response_text = response.content[0].text

    return {
        'model': model['name'],
        'model_id': model['id'],
        'backend': backend,
        'category': prompt['category'],
        'tier': prompt['tier'],
        'run_idx': run_idx,
        'timestamp': datetime.utcnow().isoformat(),
        'response_text': response_text,
        'metrics': metrics,
        'scores': None,  # Filled by score_results.py
    }
```

---

## 6. Cost Comparison Framework

### Per-Task Cost Formulae

**Frontier API cost:**
```
cost_usd = (input_tokens / 1_000_000 * input_price) + (output_tokens / 1_000_000 * output_price)
```

**Local cost:**
```
cost_per_hour_usd = 0.13  # 30W * GBP0.30/kWh + GBP2499/3yr amortised
cost_usd = total_inference_seconds * (cost_per_hour_usd / 3600)
```

At 20 tok/s: ~**$0.0018 per 1K output tokens**.

| Comparison | Local | Haiku 4.5 | Sonnet 4.6 | Opus 4.6 |
|---|---|---|---|---|
| Cost per 1K output tokens | $0.002 | $0.005 | $0.015 | $0.025 |
| Local savings factor | 1x | 2.8x | 8x | 14x |

**MDAP cost:**
```
mdap_cost = decomposition_cost + (num_subtasks * k * microagent_cost)
```

Even with k=5 and 5 subtasks (= 25 local inferences), the total MDAP cost is 25x the single-inference local cost — still far cheaper than one Sonnet call for the equivalent task.

### The Routing Matrix (Article Centrepiece)

Generated by `analysis/generate_tables.py`:

| Task | Tier | Best Local | Local Score | Haiku | Sonnet | Opus | MDAP Score | MDAP Cost | Sonnet Cost | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| Code Gen | Simple | ? | ?/5 | ?/5 | ?/5 | ?/5 | ?/5 | $? | $? | ? |
| Code Gen | Medium | ? | ?/5 | ?/5 | ?/5 | ?/5 | ?/5 | $? | $? | ? |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

---

## 7. Setup & Execution

### Prerequisites

```bash
# 1. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama --version  # Need 0.19+

# 2. Start server with persistent loading
export OLLAMA_KEEP_ALIVE="-1"
ollama serve &

# 3. Pull models (~70GB total)
for model in gemma4:e4b gemma4:26b-a4b gemma4:31b qwen3.5:9b qwen2.5-coder:14b deepseek-r1:14b mistral-small3; do
  echo "Pulling $model..."
  ollama pull $model
done

# 4. Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install aiohttp anthropic pyyaml ruff pylint sentence-transformers pytest numpy pandas fastapi uvicorn
```

### Execution

```bash
# Full benchmark
python harness/runner.py

# Single category smoke test
python harness/runner.py --model gemma4:e4b --category code_gen --tier simple

# MDAP tests only
python harness/runner.py --mdap-only

# Score, analyse, generate outputs
python analysis/score_results.py
python analysis/cost_calculator.py
python analysis/generate_tables.py
python analysis/generate_charts.py
```

### Memory Management

```bash
# Only one large model at a time on 24GB!
# The runner handles this via model_lifecycle.py, but for manual testing:
ollama stop gemma4:26b-a4b    # Unload before loading another large model
ollama run gemma4:31b

# Monitor memory pressure
while true; do memory_pressure; sleep 5; done

# Check loaded models
curl -s http://localhost:11434/api/ps | python -m json.tool
```

---

## 8. Narrative Arc for the Article

1. **The problem:** API costs scale linearly. Orgs burn budget on tasks that don't need frontier intelligence. A 70/20/10 Haiku/Sonnet/Opus split halves costs — but what if 70% of Haiku traffic could run locally for near-zero marginal cost?

2. **The hardware story:** A MacBook Pro M4 (24GB, £2,499) runs Gemma 4 26B MoE at ~20 tok/s with near-30B quality. Local cost: ~$0.002/1K tokens vs Haiku's $0.005.

3. **The quality tiers evidence:** Benchmark results showing exactly where local models match and fall short of frontier. Expected: local matches Haiku on simple tasks, falls behind on complex reasoning and long context.

4. **The MAKER insight:** Meyerson et al. showed that extreme decomposition + multi-agent voting with cheap models matches expensive frontier quality. We tested this locally: decompose with Sonnet once, then run 5 parallel local agents per subtask, vote on results. The assembled output quality approaches Sonnet at a fraction of the cost.

5. **The cost maths:** Per-task comparisons. The MDAP cost advantage. The crossover points.

6. **The routing recommendation:** Decision matrix for tech leads:
   - Simple, short-context, structured → **Local**
   - Medium complexity, decomposable → **MDAP (local + voting)**
   - Complex reasoning, long context, safety-critical → **Frontier (Sonnet/Opus)**

7. **The caveats:** Where local falls short, why 48GB is the comfort zone, why this complements frontier rather than replacing it.

---

## 9. Risks & Honest Limitations

- **24GB is tight.** Gemma 4 31B fits but context caps at 2-4K. The 26B MoE is more practical. 48GB is the real comfort zone. Own this in the article.
- **Ollama 0.19 MLX is preview.** Pin the version. Note it.
- **Gemma 4 is 3 days old.** Quantisation improvements and bug fixes are still landing. Results may improve rapidly.
- **Benchmarks are not production.** Synthetic tasks don't capture real workflow complexity.
- **Token speed matters.** A 4/5 model that takes 60s is worse than 3.5/5 in 5s for many use cases. Report latency alongside quality.
- **MDAP overhead.** Decomposition itself costs (frontier call or large local model call). For trivial tasks, MDAP is slower and costlier than direct execution. Test and show this.
- **MAKER paper scope.** The original tested Towers of Hanoi — deterministic and well-structured. Our extension to code gen and doc analysis is novel but unvalidated. Be transparent.
- **Model churn.** Date-stamp everything. Note exact model versions and Ollama version.
