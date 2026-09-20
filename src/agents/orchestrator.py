import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import asyncio
import json
from datetime import datetime
from typing import Dict, Any

from src.agents.work_history_agent import work_history_agent
from src.agents.kyc_agent import kyc_agent
from src.agents.fraud_agent import fraud_agent
from src.agents.decision_agent import decision_agent
from src.events.event_bus import event_bus

class AgentOrchestrator:
    """Orchestrates 4-Agent AI Pipeline (Agents 1, 2, 3 parallel via asyncio.gather -> Agent 4 sequential)."""

    async def process_parametric_claim_pipeline(self, worker_id: str, claim_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full 4-Agent Execution Journey with Rich Terminal Logging for Admin Demonstrations:
        1. Run Agent 1 (Work History), Agent 2 (KYC Finance), Agent 3 (Fraud) concurrently using asyncio.gather.
        2. Pass combined outputs to Agent 4 (Decision & Payout Arithmetic).
        3. Publish claim result to Async Event Bus (simulating Kafka 'claim.raised' topic).
        """
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("\n" + "=" * 80)
        print("          GIGEASE AI — 4-AGENT PARAMETRIC CLAIM DECISION ENGINE LOG")
        print("=" * 80)
        print(f"[{timestamp_str}] CLAIM EVENT INITIATED")
        print(f"  > Worker ID: {worker_id}")
        print(f"  > Zone ID  : {claim_context.get('zone_id', 'ZONE_MAA_01')}")
        print(f"  > Disruption Event: {claim_context.get('disruption_event_type', 'STFI_Heavy_Rainfall')}")
        print("-" * 80)

        # Step 1: Run Agents 1, 2, 3 in parallel
        a1_task = work_history_agent.evaluate_work_history(worker_id, claim_context)
        a2_task = kyc_agent.verify_kyc_and_policy(worker_id, claim_context)
        a3_task = fraud_agent.assemble_fraud_score(worker_id, claim_context)

        agent1_res, agent2_res, agent3_res = await asyncio.gather(a1_task, a2_task, a3_task)

        # Print Agent 1 Log
        print("[AGENT 1: WORK HISTORY & ISOLATION FOREST]")
        print(f"  > Baseline Activity Check : Verified ({agent1_res['status']})")
        print(f"  > Work History Fraud Score: {agent1_res['work_history_score']}")
        print(f"  > Flags Triggered        : {agent1_res['flags']}")
        print("-" * 80)

        # Print Agent 2 Log
        print("[AGENT 2: DIGILOCKER KYC & NPCI UPI]")
        print(f"  > Aadhaar Verified via DigiLocker: {agent2_res['kyc_verified_flag']}")
        print(f"  > Policy Status                  : {'ACTIVE' if agent2_res['policy_active_flag'] else 'INACTIVE'}")
        print(f"  > NPCI UPI VPA Valid             : {agent2_res['upi_vpa_valid']}")
        print(f"  > Eligibility Score              : {agent2_res['financial_eligibility_score']}")
        print("-" * 80)

        # Print Agent 3 Log
        print("[AGENT 3: 17-CHECK FRAUD ASSEMBLY & GPS ANTI-SPOOFING]")
        print(f"  > Overall Fraud Score     : {agent3_res['overall_fraud_score']}")
        print(f"  > Recommended Action       : {agent3_res['recommended_action']}")
        print(f"  > Fraud Signals Triggered  : {agent3_res['fraud_signals_triggered']}")
        print("-" * 80)

        # Step 2: Run Agent 4 sequentially
        final_decision = decision_agent.calculate_and_authorize_payout(
            worker_id=worker_id,
            claim_context=claim_context,
            agent1_res=agent1_res,
            agent2_res=agent2_res,
            agent3_res=agent3_res
        )

        # Print Agent 4 Log
        print("[AGENT 4: DECISION & PAYOUT ARITHMETIC]")
        print(f"  > Decision Verdict  : {final_decision['decision']}")
        print(f"  > Approved Payout   : INR {final_decision['payout_amount']:.2f}")
        if "utr_number" in final_decision:
            print(f"  > Razorpay UPI UTR  : {final_decision['utr_number']}")
        print(f"  > LLM Explanation   : {final_decision['llm_explanation']}")
        print("=" * 80)
        print(f"FINAL VERDICT: {final_decision['decision']} | PAYOUT: INR {final_decision['payout_amount']:.2f}")
        print("=" * 80 + "\n")

        # Attach agent trace details
        final_decision["agent_pipeline_trace"] = {
            "agent1_work_history": agent1_res,
            "agent2_kyc_finance": agent2_res,
            "agent3_fraud_detection": agent3_res
        }

        # Step 3: Publish to Event Bus
        await event_bus.publish("claim.raised", final_decision)

        return final_decision

orchestrator = AgentOrchestrator()

if __name__ == "__main__":
    async def test_run():
        context = {
            "w_avg": 4500.0,
            "w_actual": 1039.0,
            "zone_id": "ZONE_MAA_01",
            "week_start_date": "2026-09-07",
            "disruption_event_type": "Cyclone_Dana_STFI",
            "is_cyclone_flood_active": True,
            "gps_accuracy_m": 120.0,
            "aadhaar_hash": "AADH_883377",
            "upi_id": "rajan@upi",
            "policy_status": "ACTIVE"
        }
        res = await orchestrator.process_parametric_claim_pipeline("W001", context)

    asyncio.run(test_run())
