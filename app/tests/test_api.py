"""
Integration Tests — FastAPI endpoints
======================================
Run with:  pytest app/tests/test_api.py -v

These tests spin up a real TestClient (no external server needed) and
use an in-memory SQLite so they leave no artefacts on disk.

Scope: upload → categorise → label → feedback loop → cluster.
"""

import sys
import os
import io
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


# ── App setup with isolated DB ────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    """
    Creates a TestClient backed by a temporary SQLite file.
    Patches DB path so tests are fully isolated from production data.
    """
    db_path = str(tmp_path_factory.mktemp("db") / "test_gullak.db")

    with patch("app.main.DB", db_path), \
         patch("app.observability.DB", db_path):
        from app.main import app, init_db
        init_db()
        with TestClient(app) as c:
            yield c


# ── Health check ──────────────────────────────────────────────────────────────

def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── Profile CRUD ──────────────────────────────────────────────────────────────

def test_list_profiles_returns_default(client):
    resp = client.get("/profiles")
    assert resp.status_code == 200
    profiles = resp.json()
    assert len(profiles) >= 1
    assert any(p["id"] == "default" for p in profiles)


def test_create_and_delete_profile(client):
    # Create
    resp = client.post("/profiles", json={"name": "Test User", "avatar_emoji": "🧪"})
    assert resp.status_code == 200
    pid = resp.json()["id"]

    # Verify it appears in list
    profiles = client.get("/profiles").json()
    assert any(p["id"] == pid for p in profiles)

    # Delete
    del_resp = client.delete(f"/profiles/{pid}")
    assert del_resp.json()["status"] == "deleted"


def test_cannot_delete_last_profile(client):
    """System must always have at least one profile."""
    profiles = client.get("/profiles").json()
    if len(profiles) > 1:
        pytest.skip("More than one profile exists; skip this guard test")
    pid = profiles[0]["id"]
    resp = client.delete(f"/profiles/{pid}")
    assert resp.status_code == 400


# ── Daily log ─────────────────────────────────────────────────────────────────

def test_create_daily_log_entry(client):
    resp = client.post(
        "/daily-log?profile_id=default",
        json={"item_name": "Chai", "category": "Food", "amount": 15.0, "date": "2026-04-01"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["id"].startswith("MANUAL_")


# ── Transaction label / flywheel ──────────────────────────────────────────────

def test_label_nonexistent_transaction_returns_404(client):
    resp = client.post(
        "/transactions/FAKE_ID_XYZ/label",
        json={"category": "Food", "apply_to_similar": False},
    )
    assert resp.status_code == 404


# ── Summary endpoints ─────────────────────────────────────────────────────────

def test_monthly_summary_returns_dict(client):
    resp = client.get("/summary/monthly?profile_id=default")
    assert resp.status_code == 200
    assert isinstance(resp.json(), dict)


def test_daily_summary_structure(client):
    resp = client.get("/summary/daily?profile_id=default")
    assert resp.status_code == 200
    body = resp.json()
    assert "date" in body
    assert "categories" in body
    assert "total" in body


# ── Intelligence endpoints ────────────────────────────────────────────────────

def test_subscriptions_endpoint(client):
    resp = client.get("/intelligence/subscriptions?profile_id=default")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_insights_endpoint_structure(client):
    resp = client.get("/intelligence/insights?profile_id=default")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert "mock_insight" in body
    assert "data_for_llm" in body


def test_behavioral_endpoint(client):
    resp = client.get("/intelligence/behavioral?profile_id=default")
    assert resp.status_code == 200
    body = resp.json()
    assert "late_night" in body
    assert "personality" in body


def test_other_clusters_endpoint_empty(client):
    """With no transactions, clusters should be empty."""
    resp = client.get("/intelligence/other-clusters?profile_id=default&n_clusters=3")
    assert resp.status_code == 200
    body = resp.json()
    assert "clusters" in body
    assert body["total_uncategorised"] == 0


# ── MLOps endpoints ───────────────────────────────────────────────────────────

def test_mlops_stats_endpoint(client):
    resp = client.get("/mlops/stats")
    assert resp.status_code == 200


def test_mlops_model_registry_endpoint(client):
    resp = client.get("/mlops/model-registry")
    assert resp.status_code == 200
    body = resp.json()
    assert "current_model" in body
    assert "version" in body


def test_mlops_drift_report_endpoint(client):
    resp = client.get("/mlops/drift-report?profile_id=default")
    assert resp.status_code == 200
