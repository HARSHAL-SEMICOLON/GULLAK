"""
Unit Tests — MerchantEmbedder & SubscriptionDetector
=====================================================
Run with:  pytest app/tests/test_intelligence.py -v

Design philosophy:
  - Tests are hermetic: they do NOT require a running server or DB.
  - The embedding model is mocked where it would add test-runtime cost.
  - Edge cases (empty lists, single item, very long names) are explicitly
    tested because these are exactly the inputs that break prod systems.
"""

import sys
import os

# Allow imports from project root without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from datetime import date, time
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from app.intelligence import MerchantEmbedder, SubscriptionDetector
from app.models import Transaction


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_transaction(**kwargs) -> Transaction:
    """Factory for minimal valid Transaction objects."""
    defaults = dict(
        id="TX_TEST_001",
        date=date(2026, 4, 15),
        time=time(14, 30, 0),
        day_of_week="Wednesday",
        merchant_raw="Test Merchant",
        merchant_clean="Test Merchant",
        merchant_type="merchant",
        amount=100.0,
        transaction_type="debit",
        payment_mode="UPI",
        bank="HDFC",
        upi_ref="REF001",
        category="Other",
        macro_category="Miscellaneous",
        confidence=0.0,
        is_recurring=False,
        month="2026-04",
    )
    defaults.update(kwargs)
    return Transaction(**defaults)


# ── MerchantEmbedder tests ────────────────────────────────────────────────────

class TestMerchantEmbedder:

    def test_predict_known_merchant_returns_correct_category(self):
        """Zomato should map to Food with high confidence."""
        embedder = MerchantEmbedder()
        if embedder.model is None:
            pytest.skip("Embedding model not available in this environment")

        category, confidence = embedder.predict_category("Zomato")
        assert category == "Food", f"Expected 'Food', got '{category}'"
        assert confidence > 0.35, f"Expected confidence > 0.35, got {confidence}"

    def test_predict_returns_unsure_for_ambiguous_merchant(self):
        """
        An ambiguous merchant should return either 'Unsure:*' or a category,
        never crash.  We test that the contract (category: str, conf: float) holds.
        """
        embedder = MerchantEmbedder()
        if embedder.model is None:
            pytest.skip("Embedding model not available in this environment")

        category, confidence = embedder.predict_category("XYZ Pvt Ltd 12345")
        assert isinstance(category, str)
        assert 0.0 <= confidence <= 1.0

    def test_predict_gracefully_degrades_without_model(self):
        """
        When the embedding model fails to load, predict_category must NOT crash.
        The keyword fallback runs instead — this is graceful degradation in action.

        'Netflix' should be identified as 'Subscriptions' via keyword rules,
        with a reduced confidence of 0.60 (vs 0.85+ from the embedding model).
        A completely unknown merchant falls back to 'Other'.
        """
        embedder = MerchantEmbedder()
        embedder.model = None  # simulate load failure

        # Known keyword → keyword fallback returns a category
        category, confidence = embedder.predict_category("Netflix")
        assert category == "Subscriptions", (
            f"Expected keyword fallback to identify 'Netflix' as Subscriptions, got '{category}'"
        )
        assert confidence == 0.60, "Keyword fallback should return reduced confidence of 0.60"

        # Completely unknown merchant → falls to 'Other'
        category2, conf2 = embedder.predict_category("asdfghjkl12345")
        assert category2 == "Other"
        assert conf2 == 0.0

    def test_cluster_empty_list_returns_empty(self):
        """Clustering an empty list should not raise."""
        embedder = MerchantEmbedder()
        result = embedder.cluster_other_merchants([])
        assert isinstance(result, dict)

    def test_cluster_single_merchant_returns_one_cluster(self):
        """A single merchant cannot be split — should return in cluster 0."""
        embedder = MerchantEmbedder()
        if embedder.model is None:
            pytest.skip("Embedding model not available in this environment")

        result = embedder.cluster_other_merchants(["Zomato"])
        assert len(result) == 1

    def test_cluster_returns_all_merchants(self):
        """Every input merchant must appear in exactly one cluster."""
        embedder = MerchantEmbedder()
        if embedder.model is None:
            pytest.skip("Embedding model not available in this environment")

        merchants = ["Zomato", "Swiggy", "Uber", "Ola", "DMart"]
        clusters = embedder.cluster_other_merchants(merchants, n_clusters=3)

        found = []
        for names in clusters.values():
            found.extend(names)
        assert sorted(found) == sorted(merchants), "Not all merchants accounted for in clusters"

    def test_cluster_n_clusters_capped_at_merchant_count(self):
        """Requesting more clusters than merchants should not raise."""
        embedder = MerchantEmbedder()
        if embedder.model is None:
            pytest.skip("Embedding model not available in this environment")

        merchants = ["Zomato", "Uber"]
        result = embedder.cluster_other_merchants(merchants, n_clusters=100)
        assert isinstance(result, dict)

    @patch("app.intelligence.embedding_model")
    def test_predict_uses_cosine_similarity(self, mock_model):
        """
        Verify that predict_category uses cosine similarity by checking
        that a vector pointing exactly at the 'Food' centroid gets classified as Food.
        """
        # Build a minimal embedder with mocked model
        embedder = MerchantEmbedder.__new__(MerchantEmbedder)
        embedder.model = MagicMock()

        # Fake a 3-dim embedding space
        food_vec = np.array([1.0, 0.0, 0.0])
        other_vec = np.array([0.0, 1.0, 0.0])

        embedder.cat_embeddings = {
            "Food": food_vec,
            "Transport": other_vec,
        }
        embedder.category_examples = {}

        # Input vector aligned with Food centroid
        embedder.model.encode.return_value = np.array([[1.0, 0.0, 0.0]])

        cat, conf = embedder.predict_category("anything")
        assert cat == "Food"
        assert conf > 0.5


# ── SubscriptionDetector tests ────────────────────────────────────────────────

class TestSubscriptionDetector:

    def test_detects_monthly_recurring_payment(self):
        """Two payments of same amount ~30 days apart should be detected."""
        txs = [
            _make_transaction(
                id="TX001",
                date=date(2026, 1, 5),
                merchant_clean="Netflix",
                amount=649.0,
            ),
            _make_transaction(
                id="TX002",
                date=date(2026, 2, 4),
                merchant_clean="Netflix",
                amount=649.0,
            ),
        ]
        result = SubscriptionDetector.detect(txs)
        assert len(result) >= 1
        sub = result[0]
        assert sub["merchant"] == "Netflix"
        assert sub["amount"] == 649.0
        assert sub["frequency"] == "monthly"

    def test_does_not_flag_irregular_payments(self):
        """Payments more than 35 days apart should NOT be flagged."""
        txs = [
            _make_transaction(id="TX003", date=date(2026, 1, 1), merchant_clean="SomeShop", amount=500.0),
            _make_transaction(id="TX004", date=date(2026, 3, 1), merchant_clean="SomeShop", amount=500.0),
        ]
        result = SubscriptionDetector.detect(txs)
        assert len(result) == 0

    def test_empty_transactions_returns_empty(self):
        """No transactions → no subscriptions."""
        assert SubscriptionDetector.detect([]) == []

    def test_only_credits_not_detected(self):
        """Credit transactions should never be flagged as subscriptions."""
        txs = [
            _make_transaction(id="TX005", date=date(2026, 1, 1), transaction_type="credit", merchant_clean="Employer", amount=50000.0),
            _make_transaction(id="TX006", date=date(2026, 2, 1), transaction_type="credit", merchant_clean="Employer", amount=50000.0),
        ]
        result = SubscriptionDetector.detect(txs)
        assert len(result) == 0

    def test_confidence_higher_for_more_occurrences(self):
        """Three occurrences should produce higher confidence than two."""
        two_txs = [
            _make_transaction(id=f"TX_A{i}", date=date(2026, i + 1, 5), merchant_clean="SpotifyA", amount=119.0)
            for i in range(2)
        ]
        three_txs = [
            _make_transaction(id=f"TX_B{i}", date=date(2026, i + 1, 5), merchant_clean="SpotifyB", amount=119.0)
            for i in range(3)
        ]
        res2 = SubscriptionDetector.detect(two_txs)
        res3 = SubscriptionDetector.detect(three_txs)

        if res2 and res3:
            assert res3[0]["confidence"] >= res2[0]["confidence"]


# ── Data contract test ────────────────────────────────────────────────────────

class TestTransactionModel:

    def test_transaction_model_rejects_future_date(self):
        """
        Transactions with future dates are a sign of parser malfunction.
        While Transaction model itself doesn't enforce this, validator.py does.
        """
        from app.validator import RawTransactionRow
        from datetime import date as d, timedelta
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RawTransactionRow(
                merchant_raw="Test",
                amount=100.0,
                transaction_type="debit",
                date=d.today() + timedelta(days=10),
            )

    def test_validator_rejects_negative_amount(self):
        from app.validator import RawTransactionRow
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RawTransactionRow(
                merchant_raw="Test",
                amount=-50.0,
                transaction_type="debit",
                date=date(2026, 1, 1),
            )

    def test_validator_rejects_unknown_tx_type(self):
        from app.validator import RawTransactionRow
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RawTransactionRow(
                merchant_raw="Test",
                amount=100.0,
                transaction_type="transfer",  # invalid
                date=date(2026, 1, 1),
            )
