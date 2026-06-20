"""
Observability module — Gullak MLOps Layer
=========================================
Logs prediction latency, confidence distributions, and data-drift signals
to a local SQLite table (`ml_events`).  All data is query-able via the
/mlops/* endpoints in main.py.

Design decisions:
  - Synchronous writes (fire-and-forget pattern via threading) to avoid
    blocking the request path.  Worst-case loss: one event row on crash,
    which is acceptable for telemetry.
  - No external dependency (no Prometheus / OpenTelemetry) so that any
    interviewer can `pip install` and run the project without extra infra.
"""

import sqlite3
import time
import json
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from functools import wraps

DB = "gullak.db"


# ── Schema bootstrap ──────────────────────────────────────────────────────────

_INIT_SQL = """
CREATE TABLE IF NOT EXISTS ml_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT NOT NULL,           -- 'prediction' | 'drift_check' | 'model_load'
    model_name  TEXT,
    latency_ms  REAL,
    confidence  REAL,
    category    TEXT,
    merchant    TEXT,
    metadata    TEXT,                    -- JSON blob for extra fields
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ml_events_type ON ml_events(event_type);
CREATE INDEX IF NOT EXISTS idx_ml_events_ts   ON ml_events(created_at);
"""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    for stmt in _INIT_SQL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass
    conn.commit()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


# ── Core logging helpers ──────────────────────────────────────────────────────

def _log_async(event_type: str, **kwargs) -> None:
    """Fire-and-forget write so the request path is never blocked."""
    def _write():
        try:
            conn = _get_conn()
            conn.execute(
                """INSERT INTO ml_events
                       (event_type, model_name, latency_ms, confidence,
                        category, merchant, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    event_type,
                    kwargs.get("model_name"),
                    kwargs.get("latency_ms"),
                    kwargs.get("confidence"),
                    kwargs.get("category"),
                    kwargs.get("merchant"),
                    json.dumps(kwargs.get("metadata")) if kwargs.get("metadata") else None,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as exc:  # noqa: BLE001
            # Telemetry must NEVER crash the main application.
            print(f"[observability] write failed: {exc}")

    threading.Thread(target=_write, daemon=True).start()


def log_prediction(
    merchant: str,
    category: str,
    confidence: float,
    latency_ms: float,
    model_name: str = "MiniLM-L6-v2",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Record a single categorisation prediction event."""
    _log_async(
        "prediction",
        model_name=model_name,
        latency_ms=latency_ms,
        confidence=confidence,
        category=category,
        merchant=merchant,
        metadata=metadata,
    )


def log_drift_check(result: Dict[str, Any], model_name: str = "parser") -> None:
    """Record the outcome of a data-drift / schema validation check."""
    _log_async(
        "drift_check",
        model_name=model_name,
        metadata=result,
    )


def log_model_load(model_name: str, latency_ms: float, success: bool) -> None:
    """Record how long the embedding model took to initialise."""
    _log_async(
        "model_load",
        model_name=model_name,
        latency_ms=latency_ms,
        metadata={"success": success},
    )


# ── Decorator ─────────────────────────────────────────────────────────────────

def timed_prediction(model_name: str = "MiniLM-L6-v2"):
    """
    Decorator that wraps a function whose return is (category, confidence)
    and automatically logs the latency + outcome.

    Usage::

        @timed_prediction(model_name="MiniLM-L6-v2")
        def predict_category(self, merchant_name):
            ...
            return category, confidence
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            result = fn(*args, **kwargs)
            latency_ms = (time.perf_counter() - t0) * 1000

            # Extract merchant from first positional arg after `self`
            merchant = args[1] if len(args) > 1 else "unknown"
            category, confidence = result if isinstance(result, tuple) else (str(result), 0.0)

            log_prediction(
                merchant=str(merchant),
                category=str(category),
                confidence=float(confidence),
                latency_ms=round(latency_ms, 3),
                model_name=model_name,
            )
            return result

        return wrapper
    return decorator


# ── Analytics helpers (used by /mlops/stats endpoint) ────────────────────────

def get_prediction_stats(db_path: str = DB) -> Dict[str, Any]:
    """
    Returns aggregated prediction telemetry:
      - p50 / p95 / p99 latencies
      - avg confidence per category
      - category distribution
      - count of Unsure / Other predictions (proxy for model quality)
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        "SELECT latency_ms, confidence, category FROM ml_events WHERE event_type='prediction'"
    ).fetchall()

    if not rows:
        conn.close()
        return {"message": "No prediction events recorded yet."}

    import numpy as np

    latencies = [r["latency_ms"] for r in rows if r["latency_ms"] is not None]
    confidences = [r["confidence"] for r in rows if r["confidence"] is not None]
    categories = [r["category"] for r in rows if r["category"]]

    cat_counts: Dict[str, int] = {}
    cat_conf: Dict[str, list] = {}
    for cat in categories:
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    for r in rows:
        if r["category"] and r["confidence"] is not None:
            cat_conf.setdefault(r["category"], []).append(r["confidence"])

    avg_conf_by_cat = {cat: round(float(np.mean(vals)), 3) for cat, vals in cat_conf.items()}

    unsure_count = sum(1 for c in categories if c.startswith("Unsure"))
    other_count = sum(1 for c in categories if c == "Other")

    conn.close()

    return {
        "total_predictions": len(rows),
        "latency_ms": {
            "p50": round(float(np.percentile(latencies, 50)), 2) if latencies else None,
            "p95": round(float(np.percentile(latencies, 95)), 2) if latencies else None,
            "p99": round(float(np.percentile(latencies, 99)), 2) if latencies else None,
        },
        "avg_confidence": round(float(np.mean(confidences)), 3) if confidences else None,
        "category_distribution": cat_counts,
        "avg_confidence_by_category": avg_conf_by_cat,
        "quality_signals": {
            "unsure_predictions": unsure_count,
            "other_predictions": other_count,
            "unsure_pct": round(unsure_count / max(len(rows), 1) * 100, 1),
            "other_pct": round(other_count / max(len(rows), 1) * 100, 1),
        },
    }
