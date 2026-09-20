import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "GigEase AI" in data["platform"]

def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert data["pool_balance_inr"] > 0.0

def test_quote_endpoint():
    payload = {
        "worker_id": "W001",
        "zone_id": "ZONE_MAA_01",
        "zone_tier": "Metro",
        "persona_category": "Food_Delivery",
        "vehicle_type": "Scooter",
        "weekly_history": [4100, 4200, 4300, 4150, 4400, 4500]
    }
    response = client.post("/api/v1/quote", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "quote_id" in data
    assert data["weekly_premium_amount_inr"] > 0.0
    assert data["w_expected_inr"] > 4000.0

import uuid

def test_claims_process_endpoint():
    worker_id = f"W_API_{uuid.uuid4().hex[:6]}"
    payload = {
        "worker_id": worker_id,
        "zone_id": "ZONE_MAA_01",
        "week_start_date": "2025-11-05",
        "disruption_event_type": "Cyclone_Dana_STFI",
        "w_avg": 4500.0,
        "w_actual": 1039.0,
        "is_mocked_location": False,
        "is_cyclone_flood_active": True,
        "gps_accuracy_m": 120.0,
        "aadhaar_hash": "AADH_883377",
        "upi_id": "rajan.k@upi"
    }
    response = client.post("/api/v1/claims/process", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] in ["APPROVED", "SOFT_FLAG_50PCT_PAID", "REJECTED_FRAUD_DETECTED"]
    assert "agent_pipeline_trace" in data

def test_payout_simulate_endpoint():
    payload = {
        "claim_id": "CLM_TEST_001",
        "worker_id": "W001",
        "amount_inr": 2422.70
    }
    response = client.post("/api/v1/payouts/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["utr_number"].startswith("RZNP")

def test_claims_history_endpoint():
    response = client.get("/api/v1/claims/history")
    assert response.status_code == 200
    data = response.json()
    assert "total_count" in data
    assert "claims" in data

def test_pool_summary_analytics_endpoint():
    response = client.get("/api/v1/analytics/pool-summary")
    assert response.status_code == 200
    data = response.json()
    assert data["total_pool_balance_inr"] > 0.0
    assert data["solvency_status"] == "SOLVENT_PASS"
    assert "IRDAI" in data["governance"]

def test_ml_drift_status_endpoint():
    response = client.get("/api/v1/ml/drift-status")
    assert response.status_code == 200
    data = response.json()
    assert "psi_score" in data
    assert data["alert_level"] in ["CRITICAL_RETRAIN_TRIGGER", "WARNING", "STABLE"]

