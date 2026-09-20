import pytest
import asyncio
from src.agents.orchestrator import orchestrator
from src.financials.pool_engine import MutualPoolEngine
from src.models.predict_income import income_predictor

import uuid

def test_cyclone_dana_honest_rider_approval():
    """Tests Cyclone Dana use case: Rajan K (W001) genuine flood claim -> AUTO-APPROVED Rs. 2,595.75 payout."""
    worker_id = f"W_RAJAN_{uuid.uuid4().hex[:6]}"
    claim_context = {
        "w_avg": 4500.0,
        "w_actual": 1039.0,
        "zone_id": "ZONE_MAA_01",
        "week_start_date": "2025-11-05",
        "disruption_event_type": "Cyclone_Dana_STFI",
        "is_cyclone_flood_active": True,
        "gps_accuracy_m": 120.0,
        "aadhaar_hash": "AADH_RAJAN_8833",
        "upi_id": "rajan.k@upi",
        "policy_status": "ACTIVE",
        "is_mocked_location": False,
        "peer_cluster_verified": True
    }

    res = asyncio.run(orchestrator.process_parametric_claim_pipeline(worker_id, claim_context))
    
    assert res["decision"] == "APPROVED"
    assert res["payout_amount"] == 2595.75
    assert res["payout_beta"] == 0.75
    assert "RZNP" in res["utr_number"]
    assert res["fraud_score"] < 0.30

def test_gps_spoofing_fraud_rejection():
    """Tests Fraudster Suresh M (W099) fake GPS app spoofing claim -> REJECTED."""
    claim_context = {
        "w_avg": 4500.0,
        "w_actual": 1039.0,
        "zone_id": "ZONE_MAA_01",
        "week_start_date": "2025-11-05",
        "disruption_event_type": "Cyclone_Dana_STFI",
        "is_mocked_location": True,  # Android fake GPS app (+0.60)
        "accelerometer_stationary": True,
        "gps_moving": True,          # Accel mismatch (+0.50)
        "cell_tower_distance_km": 6.2, # Cell tower mismatch (+0.35)
        "weather_discrepancy_score": 0.80, # Weather mismatch (+0.80)
        "aadhaar_hash": "AADH_SURESH_9911",
        "upi_id": "suresh@upi",
        "policy_status": "ACTIVE"
    }

    res = asyncio.run(orchestrator.process_parametric_claim_pipeline("W099", claim_context))

    assert res["decision"] == "REJECTED_FRAUD_DETECTED"
    assert res["payout_amount"] == 0.0
    assert res["fraud_score"] >= 0.70

def test_3tier_income_predictor():
    """Tests 3-Tier Income Predictor (Cold Start vs WMA Decay vs Adjusters)."""
    # Tier 1: Cold start (<4 weeks)
    t1_res = income_predictor.predict_w_expected("W_NEW", [3500.0])
    assert "Tier 1" in t1_res["tier_used"]
    assert t1_res["final_w_expected"] == 4200.0

    # Tier 3: 12-week veteran
    hist_12 = [4000]*12
    t3_res = income_predictor.predict_w_expected("W_VET", hist_12, adjusters={"festival_flag": True})
    assert "Tier 3" in t3_res["tier_used"]
    assert t3_res["final_w_expected"] == 4800.0  # 4000 * 1.20 festival surge

def test_pool_reserve_gate():
    """Tests 30% Minimum Pool Reserve Rule Gate."""
    pool_engine = MutualPoolEngine()
    pass_gate, status_msg, _ = pool_engine.check_pool_reserve_gate(1000.0)
    assert pass_gate is True
    assert status_msg == "PASS"

def test_rsmd_bandh_payout_beta_065():
    """Tests RSMD Chennai Bandh claim: Beta = 0.65 applies."""
    worker_id = f"W_RSMD_{uuid.uuid4().hex[:6]}"
    claim_context = {
        "w_avg": 4500.0,
        "w_actual": 1000.0,
        "zone_id": "ZONE_MAA_01",
        "week_start_date": "2026-09-14",
        "disruption_event_type": "Chennai_Bandh_RSMD",
        "rsmd_sources_confirmed_count": 2,
        "aadhaar_hash": "AADH_TEST_9988",
        "upi_id": "test.rider@upi",
        "policy_status": "ACTIVE"
    }
    res = asyncio.run(orchestrator.process_parametric_claim_pipeline(worker_id, claim_context))
    assert res["decision"] == "APPROVED"
    assert res["payout_beta"] == 0.65
    # Loss = 4500 - 1000 = 3500. Payout = 0.65 * 3500 = 2275.0
    assert res["payout_amount"] == 2275.0

def test_duplicate_claim_rejection():
    """Tests Level 1 duplicate claim prevention matrix."""
    worker_id = f"W_DUP_{uuid.uuid4().hex[:6]}"
    claim_context = {
        "w_avg": 4500.0,
        "w_actual": 1000.0,
        "zone_id": "ZONE_MAA_01",
        "week_start_date": "2026-09-14",
        "disruption_event_type": "Chennai_Bandh_RSMD",
        "is_duplicate_claim": True,
        "aadhaar_hash": "AADH_TEST_9988",
        "upi_id": "test.rider@upi",
        "policy_status": "ACTIVE"
    }
    res = asyncio.run(orchestrator.process_parametric_claim_pipeline(worker_id, claim_context))
    assert res["decision"] == "REJECTED_DUPLICATE_CLAIM_EXACT"
    assert res["payout_amount"] == 0.0
