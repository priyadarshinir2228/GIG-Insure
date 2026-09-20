import asyncio
from typing import Dict, Any

class WorkHistoryAgent:
    """Agent 1: Work History & Behavioral Anomaly Check (Runs in parallel via asyncio.gather)."""

    async def evaluate_work_history(self, worker_id: str, claim_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates 4-week activity baseline, pre-event manipulation, and GPS timeline continuity.
        Output: work_history_score (0.0 to 1.0) and status.
        """
        # Simulate millisecond async lookup
        await asyncio.sleep(0.01)

        acceptance_rate = claim_context.get("order_acceptance_rate", 0.92)
        refused_pre_event = claim_context.get("pre_event_refusals_count", 0)

        score = 0.04  # Clean baseline score
        flags = []

        if acceptance_rate < 0.40:
            score += 0.25
            flags.append("work_history_anomaly_drop")

        if refused_pre_event > 5:
            score += 0.30
            flags.append("pre_event_order_suppression")

        # Positive signal: Degraded GPS during proven cyclone/flood is natural, not fraud!
        if claim_context.get("is_cyclone_flood_active", False) and claim_context.get("gps_accuracy_m", 120.0) > 100.0:
            score = max(0.0, score - 0.04)
            flags.append("gps_degradation_natural_flood_signal")

        return {
            "agent_id": "Agent_1_WorkHistory",
            "work_history_score": round(score, 4),
            "status": "PASS" if score < 0.30 else "FLAGGED",
            "flags": flags
        }

work_history_agent = WorkHistoryAgent()
