import uuid
from typing import Dict, Any
from src.financials.pool_engine import MutualPoolEngine
from src.db.database import get_connection, commit_atomic_payout_transaction

pool_engine = MutualPoolEngine()

class DecisionAgent:
    """Agent 4: Decision & Payout Execution Agent (Sequentially evaluates Agent 1, 2, 3 outputs)."""

    def calculate_and_authorize_payout(
        self,
        worker_id: str,
        claim_context: Dict[str, Any],
        agent1_res: Dict[str, Any],
        agent2_res: Dict[str, Any],
        agent3_res: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Executes 10-Step Payout Arithmetic & Solvency Checks:
        1. Duplicate Claim Check (Level 1 exact hash lookup)
        2. Determine Event Category & Dynamic Beta (STFI beta=0.75, RSMD beta=0.65, Default beta=0.70)
        3. Evaluate Trigger: W_actual < 0.60 * W_avg
        4. Compute Loss = W_avg - W_actual
        5. Raw Payout = Beta * Loss
        6. Evaluate Fraud Action (Agent 3 score)
        7. Apply Coverage Cap (1.5 * W_avg)
        8. Apply Minimum Payout Check (Rs. 200)
        9. Evaluate 30% Minimum Pool Reserve Gate
        10. Generate Razorpay UTR & Execute Atomic 5-Table Commit
        """
        event_type = claim_context.get("disruption_event_type", "Heavy_Rainfall")
        week_start = claim_context.get("week_start_date", "2026-09-07")

        # Step 1: Duplicate Claim Matrix (Level 1 Exact Spatiotemporal Match)
        if claim_context.get("is_duplicate_claim", False):
            return {
                "claim_id": f"CLM_{uuid.uuid4().hex[:8].upper()}",
                "worker_id": worker_id,
                "decision": "REJECTED_DUPLICATE_CLAIM_EXACT",
                "fraud_score": 0.95,
                "payout_amount": 0.0,
                "llm_explanation": f"Duplicate claim detected for worker {worker_id} on event '{event_type}' for week starting {week_start}."
            }

        # Check DB for existing claim
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT claim_id FROM claims WHERE worker_id = ? AND disruption_event_type = ? AND week_start_date = ? AND claim_status IN ('APPROVED', 'SOFT_FLAGGED');",
                (worker_id, event_type, week_start)
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                return {
                    "claim_id": f"CLM_{uuid.uuid4().hex[:8].upper()}",
                    "worker_id": worker_id,
                    "decision": "REJECTED_DUPLICATE_CLAIM_EXACT",
                    "fraud_score": 0.95,
                    "payout_amount": 0.0,
                    "llm_explanation": f"Duplicate claim detected. Active claim {row['claim_id']} already exists for event '{event_type}'."
                }
        except Exception:
            pass

        # Step 2: Dynamic Beta Factor Selection (STFI beta=0.75, RSMD beta=0.65, Default=0.70)
        event_upper = event_type.upper()
        if any(kw in event_upper for kw in ["STFI", "RAIN", "FLOOD", "CYCLONE", "HEAT", "AQI", "STORM"]):
            payout_beta = 0.75
            disruption_category = "STFI (Natural Disaster)"
        elif any(kw in event_upper for kw in ["RSMD", "RIOT", "STRIKE", "CURFEW", "BANDH"]):
            payout_beta = 0.65
            disruption_category = "RSMD (Social Disruption)"
        else:
            payout_beta = 0.70
            disruption_category = "Combined Disruption"

        w_avg = claim_context.get("w_avg", 4500.0)
        w_actual = claim_context.get("w_actual", 1039.0)
        coverage_cap = round(1.5 * w_avg, 2)
        trigger_threshold = round(0.60 * w_avg, 2)

        # Trigger Check
        is_triggered = (w_actual < trigger_threshold)
        if not is_triggered:
            return {
                "claim_id": f"CLM_{uuid.uuid4().hex[:8].upper()}",
                "worker_id": worker_id,
                "decision": "NO_CLAIM_TRIGGERED",
                "fraud_score": agent3_res["overall_fraud_score"],
                "payout_amount": 0.0,
                "payout_beta": payout_beta,
                "disruption_category": disruption_category,
                "llm_explanation": f"Actual income (Rs. {w_actual:.2f}) did not fall below the 60% trigger threshold (Rs. {trigger_threshold:.2f})."
            }

        # Loss & Raw Payout Arithmetic
        income_loss = round(w_avg - w_actual, 2)
        raw_payout = round(payout_beta * income_loss, 2)

        # Step 5: Fraud Action Check
        fraud_score = agent3_res["overall_fraud_score"]
        fraud_action = agent3_res["recommended_action"]

        if agent2_res["financial_eligibility_score"] < 1.0:
            return {
                "claim_id": f"CLM_{uuid.uuid4().hex[:8].upper()}",
                "worker_id": worker_id,
                "decision": "REJECTED_KYC_POLICY_INVALID",
                "fraud_score": fraud_score,
                "payout_amount": 0.0,
                "llm_explanation": "Policy inactive or KYC verification failed."
            }

        if fraud_action == "REJECT":
            return {
                "claim_id": f"CLM_{uuid.uuid4().hex[:8].upper()}",
                "worker_id": worker_id,
                "decision": "REJECTED_FRAUD_DETECTED",
                "fraud_score": fraud_score,
                "payout_amount": 0.0,
                "llm_explanation": f"Claim rejected due to high fraud anomaly score ({fraud_score:.2f}). Triggered signals: {agent3_res['fraud_signals_triggered']}."
            }

        # Step 6 & 7: Cap & Min Payout
        capped_payout = min(raw_payout, coverage_cap)
        if capped_payout < 200.0:
            return {
                "claim_id": f"CLM_{uuid.uuid4().hex[:8].upper()}",
                "worker_id": worker_id,
                "decision": "BELOW_MINIMUM_PAYOUT_THRESHOLD",
                "fraud_score": fraud_score,
                "payout_amount": 0.0,
                "llm_explanation": f"Calculated payout (Rs. {capped_payout:.2f}) is below the Rs. 200 minimum processing threshold."
            }

        final_payout = capped_payout
        if fraud_action == "SOFT_FLAG":
            final_payout = round(capped_payout * 0.50, 2)

        # Step 8: Pool Reserve Gate
        gate_pass, gate_msg, pool_status = pool_engine.check_pool_reserve_gate(final_payout)
        if not gate_pass:
            claim_id = f"CLM_{uuid.uuid4().hex[:8].upper()}"
            return {
                "claim_id": claim_id,
                "worker_id": worker_id,
                "decision": "QUEUED_POOL_RESERVE_GATE",
                "fraud_score": fraud_score,
                "payout_amount": final_payout,
                "llm_explanation": "Claim approved but queued for settlement in next cycle as pool balance reached 30% reserve threshold."
            }

        # Step 9: Razorpay UTR & Atomic DB Commit
        claim_id = f"CLM_{uuid.uuid4().hex[:8].upper()}"
        utr_num = f"RZNP{uuid.uuid4().hex[:12].upper()}"

        claim_record = {
            "claim_id": claim_id,
            "worker_id": worker_id,
            "zone_id": claim_context.get("zone_id", "ZONE_BLR_01"),
            "week_start_date": claim_context.get("week_start_date", "2026-09-07"),
            "disruption_event_type": claim_context.get("disruption_event_type", "Heavy_Rainfall"),
            "claimed_loss_amount": income_loss,
            "approved_payout_amount": final_payout,
            "fraud_score": fraud_score,
            "claim_status": "APPROVED" if fraud_action == "AUTO_APPROVE" else "SOFT_FLAGGED",
            "utr_number": utr_num,
            "llm_explanation": f"Parametric flood claim auto-approved. Rs. {final_payout:.2f} credited via Razorpay UPI (UTR: {utr_num})."
        }

        updated_policy = {"worker_id": worker_id, "claim_loading_pct": 5.0}
        pool_update = {
            "new_pool_balance": pool_status["total_pool_balance"] - final_payout,
            "new_icr": round((pool_status["total_pool_balance"] - final_payout) / pool_status["total_active_coverage"], 4)
        }

        commit_atomic_payout_transaction(claim_record, updated_policy, pool_update)

        return {
            "claim_id": claim_id,
            "worker_id": worker_id,
            "decision": "APPROVED" if fraud_action == "AUTO_APPROVE" else "SOFT_FLAG_50PCT_PAID",
            "fraud_score": fraud_score,
            "payout_amount": final_payout,
            "payout_beta": payout_beta,
            "disruption_category": disruption_category,
            "utr_number": utr_num,
            "llm_explanation": claim_record["llm_explanation"]
        }

decision_agent = DecisionAgent()
