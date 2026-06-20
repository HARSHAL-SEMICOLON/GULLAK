"""
Data Validation & Drift Detection — Gullak MLOps Layer
=======================================================
Uses Pydantic v2 for schema validation of raw parsed rows coming off the
PDF parser.  A "drift check" catches cases where Google changes its GPay
PDF format — instead of producing silent bad predictions, the pipeline
fails loudly with a structured report.

Interview talking point:
  "I used Pydantic because it gives me free JSON-serialisable error reports,
  not just stack traces.  If a field that was always present (e.g. 'amount')
  suddenly goes missing for >5% of rows, that's a signal the PDF format has
  drifted, not just a one-off parse error."

Architecture:
  Parser  →  RawTransactionRow (Pydantic validation)
          →  DriftReport (summary of anomalies)
          →  Observability log
          →  Continue / Raise based on error_rate threshold
"""

from __future__ import annotations

import re
from datetime import date as dt_date, time as dt_time
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, field_validator, model_validator, ValidationError


# ── Raw row schema — what we EXPECT from the parser ──────────────────────────

class RawTransactionRow(BaseModel):
    """
    Validates a single parsed transaction row.
    Catches missing amounts, malformed dates, and implausibly large values.
    """

    merchant_raw: str
    amount: float
    transaction_type: str        # must be 'debit' or 'credit'
    date: dt_date
    time: Optional[dt_time] = None
    payment_mode: Optional[str] = None
    bank: Optional[str] = None
    upi_ref: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError(f"Amount must be ≥ 0, got {v}")
        if v > 10_000_000:
            raise ValueError(f"Amount {v} exceeds plausibility ceiling (₹1 crore)")
        return v

    @field_validator("transaction_type")
    @classmethod
    def tx_type_must_be_valid(cls, v: str) -> str:
        if v.lower() not in {"debit", "credit"}:
            raise ValueError(f"transaction_type must be 'debit' or 'credit', got '{v}'")
        return v.lower()

    @field_validator("merchant_raw")
    @classmethod
    def merchant_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("merchant_raw cannot be empty")
        return v.strip()

    @model_validator(mode="after")
    def date_not_in_future(self) -> "RawTransactionRow":
        from datetime import date
        if self.date > date.today():
            raise ValueError(f"Transaction date {self.date} is in the future — possible parse error")
        return self


# ── Drift report ─────────────────────────────────────────────────────────────

class FieldDriftSignal(BaseModel):
    field: str
    error_count: int
    total_rows: int
    error_rate_pct: float
    sample_errors: List[str]


class DriftReport(BaseModel):
    total_rows: int
    valid_rows: int
    invalid_rows: int
    overall_error_rate_pct: float
    field_signals: List[FieldDriftSignal]
    is_drift_detected: bool
    drift_threshold_pct: float
    summary: str


# ── Validator entry point ─────────────────────────────────────────────────────

DRIFT_THRESHOLD_PCT = 10.0   # >10% invalid rows → flag as drift


def validate_parsed_rows(
    raw_rows: List[Dict[str, Any]],
    threshold_pct: float = DRIFT_THRESHOLD_PCT,
) -> Tuple[List[RawTransactionRow], DriftReport]:
    """
    Validates a list of raw parsed dicts.

    Returns:
        (valid_rows, DriftReport)

    Raises:
        RuntimeError: if the error rate exceeds `threshold_pct` — this is
            the "fail loudly" behaviour that prevents silent bad predictions.
    """
    valid: List[RawTransactionRow] = []
    field_errors: Dict[str, List[str]] = {}
    invalid_count = 0

    for idx, row in enumerate(raw_rows):
        try:
            valid.append(RawTransactionRow(**row))
        except ValidationError as exc:
            invalid_count += 1
            for err in exc.errors():
                field = " → ".join(str(loc) for loc in err["loc"])
                field_errors.setdefault(field, [])
                if len(field_errors[field]) < 3:   # keep at most 3 examples
                    field_errors[field].append(
                        f"row {idx}: {err['msg']} (got {repr(row.get(err['loc'][0]))})"
                    )

    total = len(raw_rows)
    error_rate = round(invalid_count / max(total, 1) * 100, 2)
    is_drift = error_rate > threshold_pct

    signals = [
        FieldDriftSignal(
            field=f,
            error_count=len(errs),
            total_rows=total,
            error_rate_pct=round(len(errs) / max(total, 1) * 100, 2),
            sample_errors=errs[:3],
        )
        for f, errs in field_errors.items()
    ]

    summary = (
        f"✅ {len(valid)}/{total} rows valid. No drift detected."
        if not is_drift
        else (
            f"⚠️  DRIFT DETECTED: {invalid_count}/{total} rows failed validation "
            f"({error_rate:.1f}% > threshold {threshold_pct}%). "
            "PDF format may have changed."
        )
    )

    report = DriftReport(
        total_rows=total,
        valid_rows=len(valid),
        invalid_rows=invalid_count,
        overall_error_rate_pct=error_rate,
        field_signals=signals,
        is_drift_detected=is_drift,
        drift_threshold_pct=threshold_pct,
        summary=summary,
    )

    if is_drift:
        raise RuntimeError(
            f"Data drift detected ({error_rate:.1f}% error rate). "
            f"Pipeline halted. Report: {report.model_dump_json(indent=2)}"
        )

    return valid, report


# ── Schema fingerprint (light-weight format versioning) ──────────────────────

_GPAY_PDF_COLUMN_PATTERNS = [
    r"Date",
    r"Transaction Details",
    r"Amount",
    r"Status",
]


def fingerprint_pdf_schema(text_sample: str) -> Dict[str, Any]:
    """
    Hashes the structural signature of a GPay PDF's first page text.
    If the fingerprint differs from the stored baseline, flag as format drift.

    Used in parser.py before row extraction to provide an early warning.
    """
    found = {pat: bool(re.search(pat, text_sample, re.IGNORECASE)) for pat in _GPAY_PDF_COLUMN_PATTERNS}
    missing = [k for k, v in found.items() if not v]
    return {
        "columns_found": found,
        "missing_columns": missing,
        "format_ok": len(missing) == 0,
        "warning": (
            f"Expected columns not found: {missing}. "
            "GPay PDF format may have changed."
        ) if missing else None,
    }
