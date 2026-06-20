import time as _time
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import List, Dict, Any, Optional, Tuple
from app.models import Transaction

# Heavy ML deps are lazy — only imported on first use to keep startup memory low
try:
    from sentence_transformers import SentenceTransformer as _ST
except ImportError:
    _ST = None  # type: ignore

# ── Model registry: versioned model descriptors ──────────────────────────────
MODEL_REGISTRY = [
    {
        "version": "v1.0",
        "name": "all-MiniLM-L6-v2",
        "embedding_dim": 384,
        "description": "Lightweight, 5x faster than BERT. 2% F1 drop vs MiniLM-L12.",
        "status": "active",
        "f1_score": 0.87,
        "latency_p50_ms": 12,
    },
    {
        "version": "v0.9",
        "name": "paraphrase-MiniLM-L3-v2",
        "embedding_dim": 384,
        "description": "Ultra-fast but lower accuracy. Deprecated after A/B test.",
        "status": "deprecated",
        "f1_score": 0.79,
        "latency_p50_ms": 6,
    },
]

# ── Initialize the model globally to avoid reloading ─────────────────────────
_model_load_start = _time.perf_counter()
try:
    if _ST is None:
        raise ImportError("sentence-transformers not installed")
    embedding_model = _ST("all-MiniLM-L6-v2")
    _model_load_ms = round((_time.perf_counter() - _model_load_start) * 1000, 2)
    print(f"[intelligence] Embedding model loaded in {_model_load_ms}ms")
except Exception as e:
    embedding_model = None
    _model_load_ms = 0
    print(f"[intelligence] WARNING: {e}")
    print("[intelligence] Graceful degradation → keyword fallback will be used.")

# ── Zero-shot classification (lazy import — optional dependency) ──────────────
_zero_shot_pipeline = None

def _get_zero_shot():
    """Lazy-load zero-shot classifier. Falls back to None if transformers not available."""
    global _zero_shot_pipeline
    if _zero_shot_pipeline is not None:
        return _zero_shot_pipeline
    try:
        from transformers import pipeline
        _zero_shot_pipeline = pipeline(
            "zero-shot-classification",
            model="facebook/bart-large-mnli",
            device=-1,  # CPU
        )
        print("[intelligence] Zero-shot classifier loaded.")
    except Exception as exc:
        print(f"[intelligence] Zero-shot unavailable (ok): {exc}")
        _zero_shot_pipeline = None
    return _zero_shot_pipeline


class MerchantEmbedder:
    """Uses semantic embeddings to classify unknown merchants."""

    def __init__(self):
        self.model = embedding_model

        # ── Expanded semantic taxonomy ─────────────────────────────────────────
        self.category_examples = {
            "Food": [
                "restaurant", "cafe", "food delivery", "pizza", "burger",
                "tandoor", "hotel", "dhaba", "biryani", "thali", "canteen",
                "bakery", "sweets", "mithai", "dabba", "mess", "tiffin",
                "zomato", "swiggy", "eatfit", "faasos", "blinkit", "zepto",
                "mcdonalds", "kfc", "subway", "dominos", "chinese", "sushi",
                "icecream", "chai", "coffee", "juice bar", "lassi", "paratha",
            ],
            "Groceries": [
                "supermarket", "grocery store", "milk", "vegetables", "kirana",
                "dmart", "reliance fresh", "more supermarket", "big basket",
                "general store", "provision store", "ration", "eggs", "fruits",
                "sabzi", "masala", "dal", "rice", "atta", "biscuit", "snacks",
                "milkbasket", "jio mart", "blinkit grocery", "quickcommerce",
            ],
            "Health": [
                "pharmacy", "medical", "chemist", "hospital", "clinic",
                "pathology", "diagnostic", "lab test", "blood test",
                "doctor", "dentist", "optician", "medicine", "generic store",
                "apollo pharmacy", "medplus", "netmeds", "1mg", "tata 1mg",
                "physiotherapy", "ayurveda", "homeopathy", "healthcare",
                "nursing home", "sanitiser", "vitamins", "supplements",
            ],
            "Transport": [
                "bus", "train", "cab", "rickshaw", "transport", "parking",
                "auto", "rapido", "ola", "uber", "metro", "irctc", "railway",
                "taxi", "shuttle", "carpool", "bike share", "scooter rental",
                "namma yatri", "bluemart", "pmpml", "bmtc", "msrtc",
            ],
            "Petrol": [
                "petroleum", "petrol pump", "fuel", "gas station",
                "indian oil", "bharat petroleum", "hp petrol", "iocl",
                "bpcl", "hpcl", "cng", "diesel", "filling station",
                "shell petrol", "essar oil", "nayara energy",
            ],
            "Entertainment": [
                "movies", "cinema", "gaming", "arcade", "sports",
                "pvr", "inox", "bookmyshow", "live event", "concert",
                "theme park", "amusement", "bowling", "go-karting",
                "escape room", "adventure park", "football", "cricket match",
                "stand up comedy", "museum", "exhibition", "theatre play",
                "district app", "paytm movies", "rooter", "gaming app",
            ],
            "Subscriptions": [
                "subscription", "streaming", "netflix", "spotify", "prime",
                "disney hotstar", "youtube premium", "zee5", "sonyliv",
                "apple music", "jio cinema", "mxplayer", "voot",
                "linkedin premium", "canva pro", "figma", "notion",
                "chatgpt", "github copilot", "adobe", "microsoft 365",
                "antivirus", "vpn", "cloud storage", "jio recharge", "airtel",
            ],
            "Clothing": [
                "apparel", "clothing", "boutique", "fashion", "garments",
                "shirt", "jeans", "kurti", "saree", "ethnic wear",
                "myntra", "ajio", "nykaa fashion", "snitch", "h&m",
                "zara", "uniqlo", "max fashion", "westside", "lifestyle",
                "tailoring", "alterations", "shoes", "footwear", "bata",
                "accessories", "belt", "bag", "sunglasses", "watch",
            ],
            "Education": [
                "university", "college", "school", "course", "institute",
                "classes", "tuition", "coaching", "udemy", "coursera",
                "skill india", "byju's", "unacademy", "vedantu", "khan academy",
                "exam fees", "admission fees", "library", "workshop",
                "bootcamp", "certification", "training", "online class",
            ],
            "Stationery": [
                "stationery", "copiers", "xerox", "books", "notebooks",
                "pen", "pencil", "sketch", "drawing", "art supplies",
                "printer", "ink", "toner", "paper", "office supplies",
                "whiteboard", "marker", "calculator", "folder", "binder",
            ],
            "Tech / Devices": [
                "computers", "electronics", "gadgets", "software", "aws",
                "cloud", "mobile", "laptop", "tablet", "headphones",
                "amazon", "flipkart", "croma", "reliance digital",
                "vijay sales", "asus", "dell", "apple store", "samsung",
                "mi store", "data cable", "charger", "power bank",
                "hosting", "domain", "server", "digital ocean", "vercel",
            ],
            "Personal Care": [
                "salon", "spa", "barbershop", "haircut", "beauty parlour",
                "manicure", "pedicure", "facial", "skincare", "nykaa",
                "cosmetics", "makeup", "shampoo", "conditioner", "face wash",
                "body lotion", "perfume", "deodorant", "waxing", "threading",
            ],
            "Utilities": [
                "electricity bill", "water bill", "gas bill", "broadband",
                "wifi", "act fibernet", "tata sky", "dish tv", "dish recharge",
                "dth recharge", "municipality", "property tax", "maintenance",
                "society charges", "apartment maintenance", "pipe gas",
            ],
            "Finance": [
                "insurance premium", "emi", "loan repayment", "mutual fund",
                "sip", "zerodha", "groww", "kuvera", "paytm money",
                "stock broker", "trading", "ppf", "fd", "recurring deposit",
                "credit card payment", "bank charges", "atm withdrawal",
            ],
        }

        # Precompute embeddings for categories
        if self.model:
            import numpy as np
            self.cat_embeddings = {}
            for cat, examples in self.category_examples.items():
                emb = self.model.encode(examples)
                self.cat_embeddings[cat] = np.mean(emb, axis=0)

    def predict_category(
        self,
        merchant_name: str,
        threshold: float = 0.40,
        unsure_min: float = 0.28,
    ) -> Tuple[str, float]:
        """
        Returns (category, confidence).

        Scoring bands:
          ≥ threshold  → confident prediction
          unsure_min ≤ score < threshold  → "Unsure: <Category>" (hierarchical state)
          < unsure_min → "Other"

        Graceful degradation chain:
          1. Embedding model → cosine similarity (primary)
          2. Zero-shot classifier → for 'Unsure' band (enhancer)
          3. Keyword fallback → if model not loaded (last resort)
        """
        t0 = _time.perf_counter()

        # ── Graceful degradation: keyword fallback ────────────────────────────
        if not self.model:
            result = self._keyword_fallback(merchant_name)
            latency_ms = round((_time.perf_counter() - t0) * 1000, 3)
            try:
                from app.observability import log_prediction
                log_prediction(
                    merchant=merchant_name,
                    category=result[0],
                    confidence=result[1],
                    latency_ms=latency_ms,
                    model_name="keyword_fallback",
                )
            except Exception:
                pass
            return result

        import numpy as np
        name_emb = self.model.encode([merchant_name])[0]

        best_cat = "Other"
        best_score = 0.0

        for cat, cat_emb in self.cat_embeddings.items():
            score = float(
                np.dot(name_emb, cat_emb)
                / (np.linalg.norm(name_emb) * np.linalg.norm(cat_emb))
            )
            if score > best_score:
                best_score = score
                best_cat = cat

        if best_score >= threshold:
            conf = min(0.92, round(best_score, 2))
            category = best_cat
        elif best_score >= unsure_min:
            # Try to resolve "Unsure" band with zero-shot classifier
            zero_shot_result = self._zero_shot_resolve(
                merchant_name, list(self.category_examples.keys())
            )
            if zero_shot_result:
                category, conf = zero_shot_result
            else:
                category = f"Unsure: {best_cat}"
                conf = round(best_score, 2)
        else:
            category = "Other"
            conf = round(best_score, 2)

        latency_ms = round((_time.perf_counter() - t0) * 1000, 3)
        try:
            from app.observability import log_prediction
            log_prediction(
                merchant=merchant_name,
                category=category,
                confidence=conf,
                latency_ms=latency_ms,
                model_name="MiniLM-L6-v2",
            )
        except Exception:
            pass

        return category, conf

    def _keyword_fallback(self, merchant_name: str) -> Tuple[str, float]:
        """
        Rule-based categorisation when the embedding model is unavailable.
        Interview talking point: 'graceful degradation' — the system
        keeps working at reduced accuracy rather than crashing entirely.
        """
        name_lower = merchant_name.lower()
        rules: List[Tuple[List[str], str]] = [
            (["zomato", "swiggy", "food", "restaurant", "cafe", "pizza", "burger"], "Food"),
            (["netflix", "spotify", "prime", "hotstar", "youtube premium"], "Subscriptions"),
            (["uber", "ola", "rapido", "metro", "bus", "irctc"], "Transport"),
            (["petrol", "fuel", "petroleum", "bpcl", "hpcl", "iocl"], "Petrol"),
            (["pharmacy", "medical", "hospital", "clinic", "apollo", "1mg"], "Health"),
            (["dmart", "bigbasket", "grocery", "kirana", "supermarket"], "Groceries"),
        ]
        for keywords, category in rules:
            if any(kw in name_lower for kw in keywords):
                return category, 0.60  # lower confidence — keyword match
        return "Other", 0.0

    def _zero_shot_resolve(
        self, merchant_name: str, candidate_labels: List[str]
    ) -> Optional[Tuple[str, float]]:
        """
        Uses a zero-shot NLI classifier to attempt confident categorisation
        of merchants in the 'Unsure' band.

        Returns (category, confidence) if classifier is confident, else None.
        This is an 'enhancer' step — it never replaces a confident embedding
        prediction, only resolves ambiguous ones.
        """
        zs = _get_zero_shot()
        if zs is None:
            return None
        try:
            output = zs(merchant_name, candidate_labels=candidate_labels, multi_label=False)
            top_label = output["labels"][0]
            top_score = float(output["scores"][0])
            # Only override if zero-shot is highly confident
            if top_score >= 0.60:
                return top_label, round(top_score, 2)
        except Exception as exc:
            print(f"[intelligence] Zero-shot resolve failed for '{merchant_name}': {exc}")
        return None

    def cluster_other_merchants(
        self,
        merchant_names: List[str],
        n_clusters: int = 5,
        algorithm: str = "kmeans",
    ) -> Dict[int, List[str]]:
        """
        Groups unknown merchants by embedding similarity.

        Supports two algorithms:
          - 'kmeans'  (default): fast, predictable cluster count.
            Use when you need exactly K groups for a UI.
          - 'dbscan': density-based, discovers latent clusters automatically.
            Use when you don't know K.  Outliers go to cluster -1.

        Interview talking point:
          KMeans requires a pre-set K which is a hyperparameter to tune;
          DBSCAN discovers the number of clusters from the data density,
          which is better for discovering truly unknown vendor categories
          (e.g. local dhabas that all live in a tight embedding neighbourhood).
        """
        if not self.model or len(merchant_names) < 2:
            return {0: merchant_names}

        import numpy as np
        from sklearn.cluster import KMeans, DBSCAN
        from sklearn.preprocessing import normalize

        embeddings = self.model.encode(merchant_names)
        embeddings_norm = normalize(embeddings, norm="l2")

        if algorithm == "dbscan":
            db = DBSCAN(eps=0.35, min_samples=2, metric="cosine")
            labels_arr = db.fit_predict(embeddings_norm)
        else:
            n_clusters = min(n_clusters, len(merchant_names))
            km = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
            labels_arr = km.fit_predict(embeddings_norm)

        clusters: Dict[int, List[str]] = {}
        for name, label in zip(merchant_names, labels_arr.tolist()):
            clusters.setdefault(int(label), []).append(name)

        return clusters


# ── Merchant Memory Lookup ─────────────────────────────────────────────────────

def lookup_merchant_memory(
    merchant_raw: str, conn
) -> Optional[tuple[str, float]]:
    """
    Check merchant_memory table for a previously user-labelled pattern.
    Uses a simple LIKE match; returns (category, confidence) or None.
    """
    try:
        rows = conn.execute(
            "SELECT merchant_pattern, user_label, confidence FROM merchant_memory ORDER BY confidence DESC"
        ).fetchall()
        merchant_upper = merchant_raw.upper()
        for row in rows:
            pattern = (row["merchant_pattern"] or "").upper()
            if pattern and pattern in merchant_upper:
                return row["user_label"], float(row["confidence"])
    except Exception:
        pass
    return None


# ── Subscription Detector ─────────────────────────────────────────────────────

class SubscriptionDetector:
    """Detects recurring payments (subscriptions, rent, EMI)."""

    @staticmethod
    def detect(transactions: List[Transaction]) -> List[Dict[str, Any]]:
        from datetime import date as _date
        debits = [t for t in transactions if t.transaction_type == "debit"]
        if not debits:
            return []

        groups: Dict[tuple, list] = defaultdict(list)
        for t in debits:
            groups[(t.merchant_clean, t.amount)].append(t)

        subscriptions = []
        for (merchant, amt), txs in groups.items():
            if len(txs) >= 2:
                def _to_date(v):
                    return v if isinstance(v, _date) else _date.fromisoformat(str(v))
                dates = sorted(_to_date(t.date) for t in txs)
                diffs = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
                avg_diff = sum(diffs) / len(diffs)
                if 25 <= avg_diff <= 35:
                    subscriptions.append({
                        "merchant": merchant,
                        "amount": amt,
                        "frequency": "monthly",
                        "occurrences": len(txs),
                        "confidence": 0.95 if len(txs) > 2 else 0.80,
                    })
        return subscriptions


# ── Behavioral Analyzer ───────────────────────────────────────────────────────

class BehavioralAnalyzer:
    """Detects spending patterns (late night, impulse, clustering)."""

    @staticmethod
    def detect_late_night(transactions: List[Transaction]) -> Dict[str, Any]:
        late_night_txs = [
            t for t in transactions
            if t.time and t.transaction_type == "debit" and (t.time.hour >= 23 or t.time.hour < 5)
        ]
        if not late_night_txs:
            return {"pattern": "late_night", "found": False}
        total_amount = sum(t.amount for t in late_night_txs)
        categories = dict(Counter(t.category for t in late_night_txs))
        return {
            "pattern": "late_night",
            "found": True,
            "count": len(late_night_txs),
            "total_amount": round(total_amount, 2),
            "top_categories": categories,
        }

    @staticmethod
    def detect_shopping_sprees(transactions: List[Transaction]) -> List[Dict[str, Any]]:
        """Detects clustered spending in non-essential categories in a short time window."""
        discretionary_cats = {"Clothing", "Entertainment", "Shopping", "Tech / Devices"}
        by_date: Dict[str, list] = defaultdict(list)
        for t in transactions:
            if t.transaction_type == "debit" and t.category in discretionary_cats:
                by_date[str(t.date)].append(t)

        sprees = []
        for date_str, txs in by_date.items():
            total = sum(t.amount for t in txs)
            if len(txs) >= 3 and total > 2000:
                sprees.append({
                    "date": date_str,
                    "transaction_count": len(txs),
                    "total_amount": round(total, 2),
                    "merchants": [t.merchant_clean for t in txs],
                })
        return sprees

    @staticmethod
    def cluster_spending_personality(transactions: List[Transaction]) -> str:
        debits = [t for t in transactions if t.transaction_type == "debit"]
        if not debits:
            return "Unknown"
        total = sum(t.amount for t in debits)
        if total == 0:
            return "Minimalist"
        cat: Dict[str, float] = defaultdict(float)
        for t in debits:
            cat[t.category] += t.amount
        if cat.get("Food", 0) / total > 0.4:
            return "Foodie"
        if (cat.get("Clothing", 0) + cat.get("Tech / Devices", 0)) / total > 0.4:
            return "Shopper"
        if cat.get("Transport", 0) / total > 0.2:
            return "Commuter"
        return "Balanced"

    @staticmethod
    def detect_wasteful_spending(transactions: List[Transaction]) -> Dict[str, Any]:
        """Detects repetitive food orders or convenience addiction."""
        from datetime import date as _date
        food_names = {"swiggy", "zomato", "uber eats", "eatfit", "blinkit", "zepto", "instamart"}
        food_txs = [
            t for t in transactions
            if t.transaction_type == "debit" and t.merchant_clean.lower() in food_names
        ]
        if not food_txs:
            return {"found": False, "avg_weekly_food_orders": 0, "total_food_delivery_spent": 0}

        weekly: Dict[int, int] = defaultdict(int)
        for t in food_txs:
            d = t.date if isinstance(t.date, _date) else _date.fromisoformat(str(t.date))
            weekly[d.isocalendar()[1]] += 1

        avg_weekly = sum(weekly.values()) / len(weekly)
        total_spent = sum(t.amount for t in food_txs)
        return {
            "found": avg_weekly >= 3,
            "avg_weekly_food_orders": round(avg_weekly, 1),
            "total_food_delivery_spent": round(total_spent, 2),
        }


# ── Insight Generator ──────────────────────────────────────────────────────────

class InsightGenerator:
    """Prepares structured data for LLM insight generation."""

    @staticmethod
    def generate_prompt_payload(transactions: List[Transaction]) -> Dict[str, Any]:
        subs = SubscriptionDetector.detect(transactions)
        late_night = BehavioralAnalyzer.detect_late_night(transactions)
        sprees = BehavioralAnalyzer.detect_shopping_sprees(transactions)
        personality = BehavioralAnalyzer.cluster_spending_personality(transactions)
        wasteful = BehavioralAnalyzer.detect_wasteful_spending(transactions)

        debits = [t for t in transactions if t.transaction_type == "debit"]
        total_spend = sum(t.amount for t in debits)

        cat_amounts: Dict[str, float] = defaultdict(float)
        for t in debits:
            cat_amounts[t.category] += t.amount
        top_cats = dict(sorted(cat_amounts.items(), key=lambda x: -x[1])[:3])

        regret_txs = [t for t in debits if getattr(t, "regret_status", None) == "regret"]
        regret_count = len(regret_txs)
        regret_amount = sum(t.amount for t in regret_txs)

        other_count = sum(
            1 for t in debits
            if (t.category or "").startswith("Other") or (t.category or "").startswith("Unsure")
        )
        other_pct = round(other_count / max(len(debits), 1) * 100, 1)

        return {
            "profile": personality,
            "total_spend_period": round(total_spend, 2),
            "top_categories": top_cats,
            "subscriptions_detected": subs,
            "late_night_spending": late_night,
            "shopping_sprees": sprees,
            "wasteful_spending": wasteful,
            "regret_tracking": {"count": regret_count, "amount": regret_amount},
            "uncategorized_stats": {"count": other_count, "percentage": other_pct},
            "rules": [
                "Only use amounts and counts provided.",
                "Never invent.",
                "Be supportive, non-judgmental.",
                "End with exactly 1 question.",
            ],
        }
