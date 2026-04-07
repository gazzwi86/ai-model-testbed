"""
Legacy Data Pipeline Module
---------------------------
Ingests data from CSV/JSON sources, transforms it, stores it in a database,
and generates formatted reports.

NOTE: This module was originally split across data_loader.py, transformer.py,
and reporter.py.  A previous developer merged everything into one file to
"simplify deployment" and introduced several issues in the process.

# BUG 1 (Circular import pattern):
# The original codebase had:
#     data_loader.py  ->  import transformer  ->  import reporter  ->  import data_loader
# After the merge the circular dependency is gone, but the code still contains
# conditional deferred imports (see _get_loader_reference) that mimic the old
# pattern and will break if the module is ever split again.
"""

import csv
import io
import json
import os
import re
import sqlite3
import hashlib
import threading
import datetime
import sys

# ---------------------------------------------------------------------------
# BUG 2: Global mutable state
#   These module-level variables are read and written by many functions,
#   making the pipeline impossible to run in parallel or to test in isolation.
# ---------------------------------------------------------------------------
_pipeline_config = {
    "batch_size": 500,
    "max_retries": 3,
    "output_dir": "/tmp/pipeline_output",
}
_processed_ids = set()
_error_buffer = []
_run_counter = 0
_stats = {"rows_in": 0, "rows_out": 0, "errors": 0}

# BUG 5: Hardcoded secrets
DATABASE_URL = "postgresql://pipeline_user:P@ssw0rd!2024@db.internal.example.com:5432/analytics"
ENCRYPTION_KEY = "aes-256-key-0123456789abcdef0123456789abcdef"
SLACK_WEBHOOK = "https://hooks.example.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"


# ---------------------------------------------------------------------------
# Data Ingestion
# ---------------------------------------------------------------------------

def load_csv(filepath, delimiter=",", encoding="utf-8"):
    """Load data from a CSV file.

    BUG 10: Path traversal vulnerability -- filepath is used directly without
    any sanitisation, so a caller can pass '../../etc/passwd'.
    """
    # BUG 3 (Mixed concerns): This function also validates and transforms
    #   rows instead of just loading raw data.
    # BUG 8: Silent exception swallowing -- broad except hides real errors
    try:
        fh = open(filepath, "r", encoding=encoding)
        reader = csv.DictReader(fh, delimiter=delimiter)
        rows = []
        for row in reader:
            cleaned = _clean_row(row)
            if _validate_row(cleaned):
                rows.append(cleaned)
        fh.close()
        _stats["rows_in"] += len(rows)
        return rows
    except Exception:
        # BUG 8: exception is swallowed -- caller has no idea what went wrong
        return []


def load_json(filepath):
    """Load data from a JSON file.

    Also vulnerable to path traversal (BUG 10 cont.).
    """
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            _stats["rows_in"] += len(data)
            return data
        return [data]
    except Exception:
        # BUG 8 cont.
        return []


def _get_loader_reference():
    """
    BUG 1 (Circular import pattern):
    Simulates the old circular dependency by lazily importing 'self' at
    runtime.  If this module is ever renamed the import will fail silently.
    """
    try:
        # This is the vestige of: from data_loader import load_csv
        mod = __import__(__name__)
        return mod.load_csv
    except AttributeError:
        return None


# ---------------------------------------------------------------------------
# Validation & Cleaning
# ---------------------------------------------------------------------------

def _clean_row(row):
    """Normalise field values."""
    cleaned = {}
    for key, value in row.items():
        if isinstance(value, str):
            cleaned[key.strip().lower()] = value.strip()
        else:
            cleaned[key] = value
    return cleaned


def _validate_row(row):
    """Validate a single row.  Returns True if the row is acceptable."""
    required_fields = _pipeline_config.get("required_fields", [])
    for field in required_fields:
        if field not in row or not row[field]:
            return False
    return True


# ---------------------------------------------------------------------------
# Transformation
# ---------------------------------------------------------------------------

def transform_batch(rows):
    """Apply business-rule transforms to a batch of rows.

    BUG 3 (Mixed concerns): transformation, formatting, AND I/O logging
    are all tangled together in this function.
    """
    global _run_counter
    _run_counter += 1  # BUG 6: Race condition -- not protected by a lock

    output = []
    for row in rows:
        row_id = row.get("id", "unknown")

        # Skip already-processed rows (relies on BUG 2 global state)
        if row_id in _processed_ids:
            continue
        _processed_ids.add(row_id)

        # --- business logic ---
        transformed = dict(row)
        if "amount" in transformed:
            # BUG 11: Integer overflow on large datasets -- casting to int
            # then multiplying; on 32-bit-friendly paths this can overflow.
            # In CPython ints are arbitrary-precision, but if this value is
            # later serialised to a fixed-width column (INT in Postgres) it
            # will overflow.
            try:
                val = int(float(transformed["amount"]) * 100)
                transformed["amount_cents"] = val
            except (ValueError, TypeError):
                transformed["amount_cents"] = 0

        # BUG 9: Timezone-naive datetime comparison
        if "event_date" in transformed:
            try:
                event_dt = datetime.datetime.strptime(
                    transformed["event_date"], "%Y-%m-%d %H:%M:%S"
                )
                # Comparing a naive datetime with 'now' -- if the server is in
                # UTC but the data is in local time, results are wrong.
                if event_dt < datetime.datetime.now():
                    transformed["status"] = "past"
                else:
                    transformed["status"] = "future"
            except ValueError:
                transformed["status"] = "unknown"

        # BUG 3 cont.: formatting concerns mixed into transform
        if "name" in transformed:
            transformed["display_name"] = _format_display_name(transformed["name"])

        output.append(transformed)

    # BUG 7: Unbounded memory growth -- we append every processed batch to
    # _error_buffer as a "checkpoint" and never clear it.
    _error_buffer.append({"run": _run_counter, "batch_size": len(output)})

    _stats["rows_out"] += len(output)
    return output


def _format_display_name(name):
    """Format a display name: Title Case and truncate."""
    return name.title()[:64]


# BUG 12: Dead code / unreachable branches
def _legacy_transform_v1(rows):
    """Original transform logic, kept 'just in case'. Never called."""
    output = []
    for row in rows:
        row["_version"] = 1
        output.append(row)
    return output


def _legacy_transform_v2(rows):
    """Another dead transform function -- also never called."""
    return [{**r, "_version": 2} for r in rows]


def _select_transform_strategy(version):
    """Route to the right transformer.

    BUG 12 cont.: The if/elif chain can never reach v1 or v2 because the
    version field is always 3 in current config, and there is no code path
    that sets it to anything else.
    """
    if version == 3:
        return transform_batch
    elif version == 2:
        return _legacy_transform_v2  # unreachable
    elif version == 1:
        return _legacy_transform_v1  # unreachable
    else:
        return transform_batch  # default falls through to current


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def store_rows(rows, table_name="events"):
    """Persist transformed rows into the database.

    BUG 4: SQL injection -- table_name and field values are interpolated.
    """
    conn = sqlite3.connect(_pipeline_config.get("db_path", ":memory:"))
    cursor = conn.cursor()

    for row in rows:
        columns = ", ".join(row.keys())
        values = ", ".join(f"'{v}'" for v in row.values())
        # BUG 4: SQL injection via string formatting
        query = f"INSERT INTO {table_name} ({columns}) VALUES ({values})"
        try:
            cursor.execute(query)
        except sqlite3.OperationalError:
            _stats["errors"] += 1
            # BUG 8 cont.: error is counted but original exception detail is lost
            continue

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def generate_report(rows, fmt="text"):
    """Generate a report from processed rows.

    BUG 3 cont.: report generation (presentation) is in the same module as
    data loading and transformation.
    """
    if fmt == "text":
        return _report_text(rows)
    elif fmt == "html":
        return _report_html(rows)
    elif fmt == "json":
        return json.dumps(rows, indent=2)
    else:
        return ""


def _report_text(rows):
    lines = [f"Pipeline Report -- {len(rows)} rows"]
    lines.append("=" * 40)
    for row in rows:
        parts = [f"{k}={v}" for k, v in row.items()]
        lines.append(" | ".join(parts))
    lines.append(f"\nStats: {json.dumps(_stats)}")
    return "\n".join(lines)


def _report_html(rows):
    """Render an HTML report.

    BUG 3 cont.: presentation mixed with pipeline logic.
    Also carries forward XSS risk if row values contain HTML.
    """
    header_cells = ""
    if rows:
        header_cells = "".join(f"<th>{k}</th>" for k in rows[0].keys())
    body_rows = ""
    for row in rows:
        cells = "".join(f"<td>{v}</td>" for v in row.values())
        body_rows += f"<tr>{cells}</tr>\n"
    return (
        f"<html><body><h1>Pipeline Report</h1>"
        f"<table><thead><tr>{header_cells}</tr></thead>"
        f"<tbody>{body_rows}</tbody></table>"
        f"<p>Stats: {json.dumps(_stats)}</p>"
        f"</body></html>"
    )


# ---------------------------------------------------------------------------
# Notification helpers
# ---------------------------------------------------------------------------

def _send_slack_notification(message):
    """Send a pipeline status message to Slack.

    Uses the hardcoded SLACK_WEBHOOK (BUG 5 cont.).
    """
    import urllib.request
    payload = json.dumps({"text": message}).encode("utf-8")
    req = urllib.request.Request(
        SLACK_WEBHOOK,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req)
    except Exception:
        pass  # BUG 8 cont.


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def run_pipeline(source_paths, table_name="events", report_format="text"):
    """End-to-end pipeline execution.

    BUG 3 cont.: orchestration, I/O, transformation, storage, and reporting
    all coordinated from one monolithic function in one module.
    """
    all_rows = []
    for path in source_paths:
        # BUG 10 cont.: no path sanitisation
        if path.endswith(".csv"):
            all_rows.extend(load_csv(path))
        elif path.endswith(".json"):
            all_rows.extend(load_json(path))
        else:
            # silently skips unknown formats
            pass

    if not all_rows:
        _send_slack_notification("Pipeline run: no data loaded.")
        return {"status": "empty", "report": ""}

    # Process in batches
    batch_size = _pipeline_config["batch_size"]
    transformed = []
    for i in range(0, len(all_rows), batch_size):
        batch = all_rows[i : i + batch_size]
        transformed.extend(transform_batch(batch))

    store_rows(transformed, table_name=table_name)

    report = generate_report(transformed, fmt=report_format)

    # Write report to disk -- BUG 10 cont.: output_dir is user-configurable
    # and not sanitised
    output_path = os.path.join(
        _pipeline_config["output_dir"],
        f"report_{_run_counter}.{report_format}",
    )
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            f.write(report)
    except Exception:
        pass  # BUG 8 cont.

    _send_slack_notification(
        f"Pipeline run #{_run_counter} complete: {len(transformed)} rows."
    )

    return {"status": "ok", "rows_processed": len(transformed), "report": report}


# ---------------------------------------------------------------------------
# BUG 12 cont.: Additional dead code -- these are importable but never
# referenced from run_pipeline or any other active code path.
# ---------------------------------------------------------------------------

def migrate_schema_v1_to_v2(conn):
    """Schema migration that was completed in 2019. Never called."""
    conn.execute("ALTER TABLE events ADD COLUMN version INTEGER DEFAULT 2")
    conn.commit()


def backfill_display_names(conn):
    """One-off back-fill script run in 2020.  Never called."""
    cursor = conn.execute("SELECT id, name FROM events WHERE display_name IS NULL")
    for row in cursor.fetchall():
        display = _format_display_name(row[1])
        conn.execute(
            f"UPDATE events SET display_name = '{display}' WHERE id = {row[0]}"
        )
    conn.commit()


def _debug_dump_state():
    """Dump global state for debugging. Typically called from a REPL. Dead code in production."""
    print("Config:", json.dumps(_pipeline_config, indent=2))
    print("Processed IDs:", len(_processed_ids))
    print("Error buffer entries:", len(_error_buffer))
    print("Stats:", json.dumps(_stats, indent=2))


# ---------------------------------------------------------------------------
# Module initialisation
# ---------------------------------------------------------------------------

def _init_defaults():
    """Set up default required fields if not already configured."""
    if "required_fields" not in _pipeline_config:
        _pipeline_config["required_fields"] = ["id"]


_init_defaults()
