from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from app.parser import parse_gpay_statement
from app.models import Transaction, Goal, Budget, DailyLogRequest, RegretUpdateRequest, Profile
import uuid
import hashlib
from datetime import datetime, date
from app.intelligence import SubscriptionDetector, BehavioralAnalyzer, InsightGenerator, MerchantEmbedder, MODEL_REGISTRY
from app.observability import get_prediction_stats, log_model_load
from app.validator import validate_parsed_rows, fingerprint_pdf_schema, DriftReport
from app.llm import get_groq_insight
import sqlite3
import tempfile
import os
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Gullak API", version="3.0")

_CORS_DEFAULTS = "http://localhost:3000,http://127.0.0.1:3000"
_allowed_origins = os.getenv("ALLOWED_ORIGINS", _CORS_DEFAULTS).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _allowed_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB = "gullak.db"

def get_conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Profiles table
    c.execute("""
    CREATE TABLE IF NOT EXISTS profiles (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        avatar_emoji TEXT DEFAULT '👤',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    # Transactions table (with profile_id)
    c.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id TEXT PRIMARY KEY,
        date TEXT,
        time TEXT,
        day_of_week TEXT,
        merchant_raw TEXT,
        merchant_clean TEXT,
        merchant_type TEXT,
        amount REAL,
        transaction_type TEXT,
        payment_mode TEXT,
        bank TEXT,
        upi_ref TEXT,
        category TEXT,
        user_label TEXT,
        macro_category TEXT,
        confidence REAL,
        flag TEXT,
        is_recurring INTEGER,
        month TEXT,
        regret_status TEXT,
        profile_id TEXT,
        source TEXT DEFAULT 'pdf'
    )""")

    # Goals table (with profile_id)
    c.execute("""
    CREATE TABLE IF NOT EXISTS goals (
        id TEXT PRIMARY KEY,
        name TEXT,
        target_amount REAL,
        current_amount REAL,
        deadline TEXT,
        profile_id TEXT
    )""")

    # Budgets table (with profile_id)
    c.execute("""
    CREATE TABLE IF NOT EXISTS budgets (
        id TEXT PRIMARY KEY,
        category TEXT,
        target_amount REAL,
        spent_amount REAL,
        month TEXT,
        profile_id TEXT
    )""")

    # Merchant memory
    c.execute("""
    CREATE TABLE IF NOT EXISTS merchant_memory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        merchant_pattern TEXT UNIQUE,
        amount_min REAL,
        amount_max REAL,
        time_pattern TEXT,
        user_label TEXT,
        macro_category TEXT,
        confidence REAL DEFAULT 1.0,
        source TEXT DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        times_applied INTEGER DEFAULT 0
    )""")

    # Safe migrations for existing DBs
    migrations = [
        "ALTER TABLE transactions ADD COLUMN regret_status TEXT",
        "ALTER TABLE transactions ADD COLUMN profile_id TEXT",
        "ALTER TABLE transactions ADD COLUMN source TEXT DEFAULT 'pdf'",
        "ALTER TABLE goals ADD COLUMN profile_id TEXT",
        "ALTER TABLE budgets ADD COLUMN profile_id TEXT",
        # merchant_memory: make pattern unique so ON CONFLICT works
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_mm_pattern ON merchant_memory(merchant_pattern)",
    ]
    for sql in migrations:
        try:
            c.execute(sql)
        except sqlite3.OperationalError:
            pass

    # Create default profile if none exist
    existing = c.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
    if existing == 0:
        c.execute(
            "INSERT INTO profiles (id, name, avatar_emoji) VALUES (?, ?, ?)",
            ("default", "My Profile", "👤")
        )
        # Migrate existing transactions to default profile
        c.execute("UPDATE transactions SET profile_id='default' WHERE profile_id IS NULL")
        c.execute("UPDATE goals SET profile_id='default' WHERE profile_id IS NULL")
        c.execute("UPDATE budgets SET profile_id='default' WHERE profile_id IS NULL")

    conn.commit()
    conn.close()


@app.on_event("startup")
def on_startup():
    init_db()
    # Log model load event for observability
    from app.intelligence import embedding_model, _model_load_ms
    log_model_load(
        model_name="all-MiniLM-L6-v2",
        latency_ms=_model_load_ms,
        success=embedding_model is not None,
    )


# ── HELPERS ──────────────────────────────────────────────────────────────────

def rows_to_transactions(rows) -> List[Transaction]:
    txs = []
    for r in rows:
        d = dict(r)
        d["is_recurring"] = bool(d.get("is_recurring", 0))
        if not d.get("time"):
            d["time"] = "00:00:00"
        # Handle profile_id not in old Transaction model gracefully
        d.setdefault("profile_id", None)
        txs.append(Transaction(**d))
    return txs


# ── PROFILES ─────────────────────────────────────────────────────────────────

@app.get("/profiles", response_model=List[Profile])
def list_profiles():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM profiles ORDER BY created_at ASC").fetchall()
    conn.close()
    return [Profile(**dict(r)) for r in rows]


@app.post("/profiles", response_model=Profile)
def create_profile(profile: Profile):
    pid = f"profile_{uuid.uuid4().hex[:8]}"
    conn = get_conn()
    conn.execute(
        "INSERT INTO profiles (id, name, avatar_emoji) VALUES (?, ?, ?)",
        (pid, profile.name, profile.avatar_emoji or "👤")
    )
    conn.commit()
    row = conn.execute("SELECT * FROM profiles WHERE id=?", (pid,)).fetchone()
    conn.close()
    return Profile(**dict(row))


@app.delete("/profiles/{profile_id}")
def delete_profile(profile_id: str):
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
    if count <= 1:
        conn.close()
        raise HTTPException(status_code=400, detail="Cannot delete the last profile.")
    conn.execute("DELETE FROM transactions WHERE profile_id=?", (profile_id,))
    conn.execute("DELETE FROM goals WHERE profile_id=?", (profile_id,))
    conn.execute("DELETE FROM budgets WHERE profile_id=?", (profile_id,))
    conn.execute("DELETE FROM profiles WHERE id=?", (profile_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted", "profile_id": profile_id}


@app.get("/profiles/{profile_id}/stats")
def get_profile_stats(profile_id: str):
    conn = get_conn()
    tx_count = conn.execute(
        "SELECT COUNT(*) FROM transactions WHERE profile_id=?", (profile_id,)
    ).fetchone()[0]
    pdf_count = conn.execute(
        "SELECT COUNT(DISTINCT source) FROM transactions WHERE profile_id=? AND source != 'manual'",
        (profile_id,)
    ).fetchone()[0]
    total_spend = conn.execute(
        "SELECT SUM(amount) FROM transactions WHERE profile_id=? AND transaction_type='debit'",
        (profile_id,)
    ).fetchone()[0] or 0
    sources = conn.execute(
        "SELECT DISTINCT source FROM transactions WHERE profile_id=? AND source != 'manual'",
        (profile_id,)
    ).fetchall()
    conn.close()
    return {
        "transaction_count": tx_count,
        "pdf_count": pdf_count,
        "total_spend": round(total_spend, 2),
        "sources": [r["source"] for r in sources],
    }


# ── UPLOAD ────────────────────────────────────────────────────────────────────

@app.post("/upload")
async def upload_statement(
    file: UploadFile = File(...),
    profile_id: str = Query("default"),
):
    raw_bytes = await file.read()
    pdf_hash = hashlib.sha256(raw_bytes).hexdigest()[:16]

    # Deduplication: check if this exact PDF was already ingested for this profile
    conn = get_conn()
    existing = conn.execute(
        "SELECT COUNT(*) FROM transactions WHERE profile_id=? AND source=?",
        (profile_id, f"hash:{pdf_hash}"),
    ).fetchone()[0]
    conn.close()
    if existing > 0:
        return {
            "status": "duplicate",
            "message": "This PDF has already been uploaded.",
            "count": 0,
            "source": f"hash:{pdf_hash}",
        }

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(raw_bytes)
        tmp_path = tmp.name

    # Use content-hash as the source tag so re-uploads of same file are idempotent
    source_tag = f"hash:{pdf_hash}"

    try:
        transactions = parse_gpay_statement(tmp_path)
        conn = get_conn()
        c = conn.cursor()
        for tx in transactions:
            c.execute("""
            INSERT OR REPLACE INTO transactions (
                id, date, time, day_of_week, merchant_raw, merchant_clean,
                merchant_type, amount, transaction_type, payment_mode, bank,
                upi_ref, category, user_label, macro_category, confidence, flag,
                is_recurring, month, regret_status, profile_id, source
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                tx.id, tx.date.isoformat(),
                tx.time.isoformat() if tx.time else None,
                tx.day_of_week, tx.merchant_raw, tx.merchant_clean, tx.merchant_type,
                tx.amount, tx.transaction_type, tx.payment_mode, tx.bank, tx.upi_ref,
                tx.category, tx.user_label, tx.macro_category, tx.confidence,
                tx.flag, int(tx.is_recurring), tx.month,
                getattr(tx, "regret_status", None),
                profile_id, source_tag,
            ))
        conn.commit()
        conn.close()
        return {"status": "success", "count": len(transactions), "source": source_tag}
    finally:
        os.unlink(tmp_path)


@app.get("/uploads")
def list_uploads(profile_id: str = Query("default")):
    """List distinct PDF sources uploaded for a profile."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT source,
               COUNT(*) as tx_count,
               MIN(date) as date_from,
               MAX(date) as date_to,
               SUM(amount) as total_amount
        FROM transactions
        WHERE profile_id=? AND source != 'manual'
        GROUP BY source
        ORDER BY date_from DESC
    """, (profile_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.delete("/uploads/{source}")
def delete_upload(source: str, profile_id: str = Query("default")):
    """Remove all transactions from a specific PDF source for a profile."""
    conn = get_conn()
    result = conn.execute(
        "DELETE FROM transactions WHERE profile_id=? AND source=?",
        (profile_id, source)
    )
    conn.commit()
    deleted = result.rowcount
    conn.close()
    return {"status": "deleted", "rows_removed": deleted, "source": source}


# ── TRANSACTIONS ──────────────────────────────────────────────────────────────

@app.get("/transactions", response_model=List[Transaction])
def get_transactions(profile_id: str = Query("default")):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM transactions WHERE profile_id=? ORDER BY date DESC, time DESC",
        (profile_id,)
    ).fetchall()
    conn.close()
    return rows_to_transactions(rows)


@app.post("/transactions/{tx_id}/regret")
def update_transaction_regret(tx_id: str, req: RegretUpdateRequest):
    conn = get_conn()
    conn.execute("UPDATE transactions SET regret_status=? WHERE id=?", (req.regret_status, tx_id))
    conn.commit()
    conn.close()
    return {"status": "success"}


class LabelRequest(BaseModel):
    category: str
    apply_to_similar: bool = True


@app.post("/transactions/{tx_id}/label")
def label_transaction(tx_id: str, req: LabelRequest):
    """
    Active-Learning Flywheel:
    1. Save the user's chosen category on the transaction.
    2. Extract the merchant_raw name and upsert it into merchant_memory
       so that future imports of the same merchant are auto-categorised.
    """
    conn = get_conn()

    # 1. Fetch the transaction
    row = conn.execute(
        "SELECT merchant_raw, macro_category FROM transactions WHERE id=?",
        (tx_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Transaction not found")

    merchant_raw = row["merchant_raw"]

    # Derive macro_category from the chosen label
    macro_mapping = {
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
    # Strip any "Unsure: " prefix the user might have confirmed
    clean_cat = req.category.replace("Unsure: ", "")
    macro = macro_mapping.get(clean_cat, "Miscellaneous")

    # 2. Update this transaction
    conn.execute(
        "UPDATE transactions SET category=?, user_label=?, macro_category=?, "
        "confidence=1.0, flag=NULL WHERE id=?",
        (clean_cat, clean_cat, macro, tx_id),
    )

    # 3. Optionally apply to all similar transactions with same merchant_raw
    updated_similar = 0
    if req.apply_to_similar:
        result = conn.execute(
            "UPDATE transactions SET category=?, user_label=?, macro_category=?, "
            "confidence=1.0, flag=NULL "
            "WHERE merchant_raw=? AND (category='Other' OR category LIKE 'Unsure:%')",
            (clean_cat, clean_cat, macro, merchant_raw),
        )
        updated_similar = result.rowcount

    # 4. Upsert into merchant_memory (flywheel)
    conn.execute(
        """
        INSERT INTO merchant_memory (merchant_pattern, user_label, macro_category, confidence, source, times_applied)
        VALUES (?, ?, ?, 1.0, 'user', 1)
        ON CONFLICT(merchant_pattern) DO UPDATE SET
            user_label=excluded.user_label,
            macro_category=excluded.macro_category,
            confidence=1.0,
            times_applied=times_applied+1
        """,
        (merchant_raw, clean_cat, macro),
    )

    conn.commit()
    conn.close()
    return {
        "status": "success",
        "merchant_pattern": merchant_raw,
        "category": clean_cat,
        "similar_updated": updated_similar,
    }


@app.delete("/transactions/clear")
def clear_all_transactions(profile_id: str = Query("default")):
    """Delete ALL transactions for a profile (nuclear option)."""
    conn = get_conn()
    result = conn.execute("DELETE FROM transactions WHERE profile_id=?", (profile_id,))
    conn.commit()
    conn.close()
    return {"status": "cleared", "rows_removed": result.rowcount}


# ── DAILY LOG ─────────────────────────────────────────────────────────────────

@app.post("/daily-log")
def create_daily_log(log: DailyLogRequest, profile_id: str = Query("default")):
    dt_obj = datetime.strptime(log.date, "%Y-%m-%d") if log.date else datetime.today()
    tx_id = f"MANUAL_{uuid.uuid4().hex[:8]}"
    conn = get_conn()
    conn.execute("""
    INSERT INTO transactions (
        id, date, time, day_of_week, merchant_raw, merchant_clean,
        merchant_type, amount, transaction_type, payment_mode, bank,
        upi_ref, category, user_label, macro_category, confidence, flag,
        is_recurring, month, regret_status, profile_id, source
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        tx_id,
        dt_obj.date().isoformat(),
        datetime.now().strftime("%H:%M:%S"),
        dt_obj.strftime("%A"),
        log.item_name, log.item_name,
        "merchant", log.amount, "debit", "cash", "Cash", "MANUAL",
        log.category, None, "Daily Notebook", 1.0, None, 0,
        dt_obj.strftime("%Y-%m"), None, profile_id, "manual",
    ))
    conn.commit()
    conn.close()
    return {"status": "success", "id": tx_id}


# ── SUMMARY ───────────────────────────────────────────────────────────────────

@app.get("/summary/monthly")
def get_monthly_summary(profile_id: str = Query("default")):
    conn = get_conn()
    rows = conn.execute("""
        SELECT month, category, SUM(amount) as total
        FROM transactions WHERE transaction_type='debit' AND profile_id=?
        GROUP BY month, category ORDER BY month DESC, total DESC
    """, (profile_id,)).fetchall()
    conn.close()
    summary: Dict = {}
    for r in rows:
        summary.setdefault(r["month"], {})[r["category"]] = r["total"]
    return summary


@app.get("/summary/daily")
def get_daily_summary(profile_id: str = Query("default")):
    today = date.today().isoformat()
    conn = get_conn()
    rows = conn.execute("""
        SELECT category, SUM(amount) as total, COUNT(*) as cnt
        FROM transactions WHERE transaction_type='debit' AND date=? AND profile_id=?
        GROUP BY category ORDER BY total DESC
    """, (today, profile_id)).fetchall()
    conn.close()
    return {
        "date": today,
        "categories": [{"category": r["category"], "total": r["total"], "count": r["cnt"]} for r in rows],
        "total": sum(r["total"] for r in rows),
    }


# ── GOALS ─────────────────────────────────────────────────────────────────────

@app.post("/goals")
def create_goal(goal: Goal, profile_id: str = Query("default")):
    goal_id = f"GOAL_{uuid.uuid4().hex[:8]}"
    deadline_str = goal.deadline.isoformat() if goal.deadline else None
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO goals (id, name, target_amount, current_amount, deadline, profile_id) VALUES (?,?,?,?,?,?)",
        (goal_id, goal.name, goal.target_amount, goal.current_amount, deadline_str, profile_id)
    )
    conn.commit()
    conn.close()
    return {"status": "success", "id": goal_id}


@app.get("/goals", response_model=List[Goal])
def get_goals(profile_id: str = Query("default")):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM goals WHERE profile_id=?", (profile_id,)).fetchall()
    conn.close()
    return [Goal(**dict(r)) for r in rows]


@app.delete("/goals/{goal_id}")
def delete_goal(goal_id: str):
    conn = get_conn()
    conn.execute("DELETE FROM goals WHERE id=?", (goal_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}


# ── BUDGETS ───────────────────────────────────────────────────────────────────

@app.post("/budgets")
def create_budget(budget: Budget, profile_id: str = Query("default")):
    budget_id = f"BUDGET_{uuid.uuid4().hex[:8]}"
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO budgets (id, category, target_amount, spent_amount, month, profile_id) VALUES (?,?,?,?,?,?)",
        (budget_id, budget.category, budget.target_amount, budget.spent_amount, budget.month, profile_id)
    )
    conn.commit()
    conn.close()
    return {"status": "success", "id": budget_id}


@app.get("/budgets", response_model=List[Budget])
def get_budgets(profile_id: str = Query("default")):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM budgets WHERE profile_id=?", (profile_id,)).fetchall()
    budgets = []
    for r in rows:
        b_dict = dict(r)
        spent_row = conn.execute(
            "SELECT SUM(amount) FROM transactions WHERE category=? AND month=? AND transaction_type='debit' AND profile_id=?",
            (b_dict["category"], b_dict["month"], profile_id)
        ).fetchone()
        b_dict["spent_amount"] = spent_row[0] or 0.0
        budgets.append(Budget(**b_dict))
    conn.close()
    return budgets


# ── INTELLIGENCE ──────────────────────────────────────────────────────────────

@app.get("/intelligence/subscriptions", response_model=List[Dict[str, Any]])
def get_subscriptions(profile_id: str = Query("default")):
    return SubscriptionDetector.detect(get_transactions(profile_id))


@app.get("/intelligence/other-clusters")
def get_other_clusters(
    profile_id: str = Query("default"),
    n_clusters: int = Query(5, ge=2, le=15),
    algorithm: str = Query("kmeans", description="'kmeans' (fixed K) or 'dbscan' (auto-discover clusters)"),
):
    """
    Clusters all transactions currently in 'Other' or 'Unsure:*' category
    using merchant name embeddings.

    Supports two algorithms:
    - **kmeans**: requires n_clusters, fast, good for a UI with a fixed number of groups.
    - **dbscan**: auto-discovers cluster count from data density.  Outliers land in cluster -1.
      Better for discovering truly unknown vendor patterns.
    """
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT DISTINCT merchant_raw
        FROM transactions
        WHERE profile_id=?
          AND (category='Other' OR category LIKE 'Unsure:%')
          AND transaction_type='debit'
        """,
        (profile_id,),
    ).fetchall()
    conn.close()

    merchant_names = [r["merchant_raw"] for r in rows]
    if not merchant_names:
        return {"clusters": {}, "total_uncategorised": 0, "algorithm": algorithm}

    embedder = MerchantEmbedder()
    clusters = embedder.cluster_other_merchants(
        merchant_names,
        n_clusters=min(n_clusters, len(merchant_names)),
        algorithm=algorithm,
    )

    # Enrich with transaction counts per cluster
    conn2 = get_conn()
    enriched = {}
    for cid, names in clusters.items():
        tx_count = 0
        total_amount = 0.0
        for name in names:
            row = conn2.execute(
                "SELECT COUNT(*) as cnt, SUM(amount) as total FROM transactions "
                "WHERE merchant_raw=? AND profile_id=?",
                (name, profile_id),
            ).fetchone()
            tx_count += row["cnt"] or 0
            total_amount += row["total"] or 0.0
        enriched[str(cid)] = {
            "merchants": names,
            "tx_count": tx_count,
            "total_amount": round(total_amount, 2),
        }
    conn2.close()

    return {
        "clusters": enriched,
        "total_uncategorised": len(merchant_names),
        "algorithm": algorithm,
        "note": "Cluster -1 (DBSCAN only) contains outliers with no dense neighbours.",
    }


@app.get("/intelligence/insights", response_model=Dict[str, Any])
def get_insights(profile_id: str = Query("default")):
    txs = get_transactions(profile_id)
    payload = InsightGenerator.generate_prompt_payload(txs)

    # Try real Groq LLM first
    insight = get_groq_insight(payload)

    # Fallback: rule-based insight when GROQ_API_KEY is not set or call fails
    if insight is None:
        late = payload["late_night_spending"]
        wasteful = payload.get("wasteful_spending", {})

        if late.get("found"):
            insight = {
                "insight_type": "behavioral",
                "title": "Late-Night Cravings Detected 🌙",
                "body": (
                    f"You have {late['count']} late-night transactions totalling "
                    f"₹{late['total_amount']}. Top category: "
                    f"{next(iter(late.get('top_categories', {})), 'unknown')}."
                ),
                "action": "Reducing late-night orders by 1/week could save ₹800+ monthly.",
                "tone": "supportive",
            }
        elif wasteful.get("found"):
            insight = {
                "insight_type": "wasteful",
                "title": "Food Delivery Habit ⚠️",
                "body": (
                    f"You average {wasteful['avg_weekly_food_orders']} food delivery orders/week, "
                    f"spending ₹{wasteful['total_food_delivery_spent']} in total."
                ),
                "action": "Cooking even 2 meals/week can save ₹1,200/month.",
                "tone": "nudge",
            }
        else:
            insight = {
                "insight_type": "summary",
                "title": "Healthy Routine ✨",
                "body": "Your spending is mostly during daytime with no major late-night spikes. Keep it up!",
                "action": None,
                "tone": "supportive",
            }

    return {"status": "success", "data_for_llm": payload, "insight": insight}


@app.get("/intelligence/behavioral")
def get_behavioral(profile_id: str = Query("default")):
    txs = get_transactions(profile_id)
    return {
        "late_night": BehavioralAnalyzer.detect_late_night(txs),
        "shopping_sprees": BehavioralAnalyzer.detect_shopping_sprees(txs),
        "wasteful": BehavioralAnalyzer.detect_wasteful_spending(txs),
        "personality": BehavioralAnalyzer.cluster_spending_personality(txs),
    }


@app.get("/health")
def health():
    from app.intelligence import embedding_model
    return {
        "status": "ok",
        "version": "3.0",
        "embedding_model": "all-MiniLM-L6-v2" if embedding_model else "none (keyword fallback)",
        "model_loaded": embedding_model is not None,
    }


# ── MLOps ENDPOINTS ─────────────────────────────────────────────────────────

@app.get("/mlops/stats")
def get_mlops_stats():
    """
    Returns aggregated prediction telemetry: p50/p95/p99 latencies,
    confidence distributions, and quality signals (Unsure %, Other %).

    Interview talking point: 'I track latency percentiles because averages
    hide tail-latency spikes. P99 > 500ms means the user feels lag.'
    """
    return get_prediction_stats(DB)


@app.get("/mlops/model-registry")
def get_model_registry():
    """
    Returns all model versions in the registry with their performance metrics.
    Active model is the one currently serving predictions.

    Interview talking point: 'Model registry lets me rollback instantly.
    If v1.1 degrades F1 by 5%, I flip the active flag and redeploy in < 1min.'
    """
    from app.intelligence import embedding_model
    active = next((m for m in MODEL_REGISTRY if m["status"] == "active"), MODEL_REGISTRY[0])
    return {
        "current_model": active["name"],
        "version": active["version"],
        "model_loaded": embedding_model is not None,
        "f1_score": active["f1_score"],
        "latency_p50_ms": active["latency_p50_ms"],
        "registry": MODEL_REGISTRY,
        "rollback_note": (
            "To rollback: change 'status' on desired version to 'active' "
            "and update SentenceTransformer model name in intelligence.py."
        ),
    }


@app.get("/mlops/drift-report")
def get_drift_report(profile_id: str = Query("default")):
    """
    Runs the data validator against the most recent 500 transactions
    and returns a drift report.

    Interview talking point: 'Silent bad predictions are worse than
    loud failures. If GPay changes its PDF format, this endpoint catches
    it before the user sees garbage categories.'
    """
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT merchant_raw, amount, transaction_type, date, time,
               payment_mode, bank, upi_ref
        FROM transactions
        WHERE profile_id=?
        ORDER BY date DESC, time DESC
        LIMIT 500
        """,
        (profile_id,),
    ).fetchall()
    conn.close()

    if not rows:
        return {"message": "No transactions found. Upload a PDF first."}

    raw_dicts = [dict(r) for r in rows]
    try:
        from app.validator import validate_parsed_rows
        _, report = validate_parsed_rows(raw_dicts)
        return report.model_dump()
    except RuntimeError as exc:
        # Drift threshold exceeded — return structured report rather than 500
        return {
            "error": "drift_detected",
            "detail": str(exc)[:500],
        }


@app.get("/mlops/experiment-log")
def get_experiment_log():
    """
    Returns a summary of all ML events logged by the observability layer.
    Includes model load times and prediction counts per model version.

    Interview talking point: 'This is my lightweight experiment tracker.
    In production I’d use MLflow, but for a portfolio project this
    keeps it dependency-free while demonstrating the same pattern.'
    """
    conn = get_conn()
    events = conn.execute(
        """
        SELECT event_type, model_name, COUNT(*) as count,
               AVG(latency_ms) as avg_latency_ms,
               MIN(created_at) as first_seen,
               MAX(created_at) as last_seen
        FROM ml_events
        GROUP BY event_type, model_name
        ORDER BY last_seen DESC
        """
    ).fetchall()
    conn.close()
    return [
        {
            "event_type": r["event_type"],
            "model_name": r["model_name"],
            "count": r["count"],
            "avg_latency_ms": round(r["avg_latency_ms"] or 0, 2),
            "first_seen": r["first_seen"],
            "last_seen": r["last_seen"],
        }
        for r in events
    ]

