import pdfplumber
import re
import uuid
import sqlite3
from datetime import datetime
from typing import List, Optional
from app.models import Transaction
from app.normalizer import normalize_merchant
from app.intelligence import MerchantEmbedder, lookup_merchant_memory

DATE_PATTERN = re.compile(r"^(\d{2}[A-Z][a-z]{2},\d{4})\s+(Paidto|Receivedfrom)(.*?)\s+₹([\d,]+\.?\d*)$")
TIME_PATTERN = re.compile(r"^(\d{2}:\d{2}[A-Z]{2})\s+(?:UPITransactionID:)(\d+)$")
BANK_PATTERN = re.compile(r"^(Paidby|Paidto)(.*)$")

DB = "gullak.db"

MACRO_MAPPING = {
    "Food": "Food & Dining",
    "Groceries": "Food & Dining",
    "Health": "Health & Wellness",
    "Transport": "Transportation",
    "Petrol": "Transportation",
    "Entertainment": "Entertainment",
    "Subscriptions": "Entertainment",
    "Clothing": "Shopping",
    "Education": "Education",
    "Stationery": "Education",
    "Tech / Devices": "Shopping",
    "Personal Care": "Personal Care",
    "Utilities": "Utilities",
    "Finance": "Finance",
    "P2P Transfer": "Transfers",
    "Other": "Miscellaneous",
}


def _get_db_conn() -> Optional[sqlite3.Connection]:
    """Open a read-only connection to merchant_memory. Returns None on failure."""
    try:
        conn = sqlite3.connect(DB)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        return None


def _resolve_unsure_category(category: str) -> str:
    """Strip 'Unsure: ' prefix to get the raw category name."""
    if category.startswith("Unsure: "):
        return category[len("Unsure: "):]
    return category


def parse_gpay_statement(pdf_path: str) -> List[Transaction]:
    transactions = []

    embedder = MerchantEmbedder()

    # Open DB once for the whole batch (merchant_memory lookup)
    db_conn = _get_db_conn()

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                lines = text.split("\n")

                i = 0
                while i < len(lines):
                    line = lines[i].strip()

                    match_date = DATE_PATTERN.match(line)
                    if match_date:
                        date_str = match_date.group(1)
                        direction = match_date.group(2)
                        merchant_raw = match_date.group(3).strip()
                        amount_str = match_date.group(4).replace(",", "")
                        amount = float(amount_str)

                        transaction_type = "debit" if direction == "Paidto" else "credit"

                        # ── Time & UPI ref ────────────────────────────────────
                        time_str = ""
                        upi_ref = ""
                        if i + 1 < len(lines):
                            match_time = TIME_PATTERN.match(lines[i + 1].strip())
                            if match_time:
                                time_str = match_time.group(1)
                                upi_ref = match_time.group(2)
                                i += 1

                        # ── Bank info ─────────────────────────────────────────
                        bank = ""
                        if i + 1 < len(lines):
                            match_bank = BANK_PATTERN.match(lines[i + 1].strip())
                            if match_bank:
                                bank = match_bank.group(2)
                                i += 1

                        # ── Parse dates ───────────────────────────────────────
                        dt_date = datetime.strptime(date_str, "%d%b,%Y").date()
                        day_of_week = dt_date.strftime("%A")
                        month = dt_date.strftime("%Y-%m")

                        dt_time_obj = None
                        if time_str:
                            dt_time_obj = datetime.strptime(time_str, "%I:%M%p").time()

                        # ══════════════════════════════════════════════════════
                        # CATEGORISATION PIPELINE (priority order):
                        #  1. merchant_memory  – user-labelled patterns (1.0 conf)
                        #  2. normalizer       – fuzzy KNOWN_MERCHANTS dict
                        #  3. ML embedder      – sentence-transformer semantic match
                        #  4. Fallback         – "Other" / "Unsure: <cat>"
                        # ══════════════════════════════════════════════════════

                        category = "Other"
                        confidence = 0.40
                        merchant_type = "unknown"

                        # 1️⃣  Merchant Memory (user-labelled, highest priority)
                        if db_conn:
                            mem_result = lookup_merchant_memory(merchant_raw, db_conn)
                            if mem_result:
                                category, confidence = mem_result
                                merchant_type = "memory"

                        # 2️⃣  Fuzzy normalizer
                        if merchant_type == "unknown":
                            merchant_clean, norm_category, norm_conf = normalize_merchant(merchant_raw)
                            if norm_category != "Other" or norm_conf > 0.45:
                                category = norm_category
                                confidence = norm_conf
                                merchant_type = "known" if norm_category != "Other" else "unknown"
                        else:
                            merchant_clean = merchant_raw  # memory hit, keep raw as clean for now

                        # 3️⃣  ML Embedder fallback (only if still uncategorised)
                        if merchant_type == "unknown" or category == "Other":
                            ml_cat, ml_conf = embedder.predict_category(merchant_raw)
                            if ml_cat != "Other":
                                category = ml_cat  # may be "Unsure: <cat>"
                                confidence = ml_conf
                                merchant_type = "ml"

                        # Re-normalise merchant_clean for memory/ml hits
                        if merchant_type in ("memory", "ml"):
                            merchant_clean, _, _ = normalize_merchant(merchant_raw)
                            if merchant_clean == merchant_raw:
                                merchant_clean = merchant_raw.title()

                        # ── Flag logic ─────────────────────────────────────────
                        flag = None
                        if category.startswith("Unsure: "):
                            flag = "unsure_category"
                        elif confidence < 0.65:
                            flag = "low_confidence"

                        if category == "P2P Transfer":
                            flag = "needs_label"

                        # ── Macro category ─────────────────────────────────────
                        base_category = _resolve_unsure_category(category)
                        macro_category = MACRO_MAPPING.get(base_category, "Miscellaneous")

                        tx = Transaction(
                            id=str(uuid.uuid4()),
                            date=dt_date,
                            time=dt_time_obj,
                            day_of_week=day_of_week,
                            merchant_raw=merchant_raw,
                            merchant_clean=merchant_clean,
                            merchant_type=merchant_type,
                            amount=amount,
                            transaction_type=transaction_type,
                            payment_mode="UPI",
                            bank=bank,
                            upi_ref=upi_ref,
                            category=category,
                            user_label=None,
                            macro_category=macro_category,
                            confidence=confidence,
                            flag=flag,
                            is_recurring=False,
                            month=month,
                        )
                        transactions.append(tx)

                    i += 1

    finally:
        if db_conn:
            db_conn.close()

    return transactions


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    txs = parse_gpay_statement("gpay_statement_20251101_20260430.pdf")
    for tx in txs[:5]:
        print(tx.model_dump_json(indent=2))
    print(f"Total parsed: {len(txs)}")
