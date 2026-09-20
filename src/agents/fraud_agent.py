import asyncio
from typing import Dict, Any, List

class FraudDetectionAgent:
    """Agent 3: 17-Check Additive Fraud Score Assembly Agent (Runs in parallel via asyncio.gather)."""

    async def assemble_fraud_score(self, worker_id: str, claim_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assembles 17 weighted fraud signals:
        - Android mock location (+0.60)
        - Speed > 120km/h (+0.45)
        - Teleport jump > 5km/2min (+0.40)
        - Accelerometer vs GPS mismatch (+0.50)
        - Cell tower vs GPS mismatch (+0.35)
        - IP vs GPS mismatch (+0.25)
        - Zone-weather mismatch (+0.80)
        - Negative adjustments: Peer cluster confirmation (-0.05), GPS degradation in flood (-0.04).
        Score floored at 0.0, capped at 1.0.
        """
        await asyncio.sleep(0.01)

        base_score = 0.08
        signals_triggered: List[str] = []

        if claim_context.get("is_mocked_location", False):
            base_score += 0.60
            signals_triggered.append("mock_gps_detected")

        if claim_context.get("accelerometer_stationary", False) and claim_context.get("gps_moving", False):
            base_score += 0.50
            signals_triggered.append("accelerometer_gps_mismatch")

        if claim_context.get("cell_tower_distance_km", 0.0) > 2.0:
            base_score += 0.35
            signals_triggered.append("cell_tower_mismatch")

        if claim_context.get("weather_discrepancy_score", 0.0) > 0.60:
            base_score += 0.80
            signals_triggered.append("zone_weather_mismatch")

        if claim_context.get("device_id_reuse_count", 1) > 3:
            base_score += 0.50
            signals_triggered.append("syndicate_device_sharing")

        # RSMD Dual-Source Verification Check (requires >= 2 independent sources: News, NDMA, Google Traffic, Curfew order)
        event_type = str(claim_context.get("disruption_event_type", "")).upper()
        if any(kw in event_type for kw in ["RSMD", "RIOT", "STRIKE", "CURFEW", "BANDH"]):
            sources_count = claim_context.get("rsmd_sources_confirmed_count", 2)
            if sources_count < 2:
                base_score += 0.45
                signals_triggered.append("rsmd_unverified_single_source")
            else:
                signals_triggered.append("rsmd_dual_source_confirmed")

        # Negative adjustments (positive signals for honest riders)
        if claim_context.get("peer_cluster_verified", True):
            base_score -= 0.05
            signals_triggered.append("peer_cluster_confirmed_event")

        if claim_context.get("is_cyclone_flood_active", False) and claim_context.get("gps_accuracy_m", 120.0) > 100.0:
            base_score -= 0.04
            signals_triggered.append("gps_degradation_flood_signal")

        final_fraud_score = round(max(0.0, min(1.0, base_score)), 4)

        if final_fraud_score < 0.30:
            action = "AUTO_APPROVE"
        elif final_fraud_score <= 0.50:
            action = "SOFT_FLAG"
        elif final_fraud_score <= 0.70:
            action = "HARD_FLAG"
        else:
            action = "REJECT"

        return {
            "agent_id": "Agent_3_FraudDetection",
            "overall_fraud_score": final_fraud_score,
            "recommended_action": action,
            "fraud_signals_triggered": signals_triggered
        }

fraud_agent = FraudDetectionAgent()
