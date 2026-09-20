import os
import sqlite3
from typing import Dict, Any, Tuple
from src.db.database import get_connection, init_db

class MutualPoolEngine:
    """Manages Mutual Risk Pool Solvency, 30% Reserve Gating, and Actuarial Rate Calculations."""
    
    MINIMUM_RESERVE_RATIO = 0.30  # 30% of total active coverage must remain in pool
    BETA_PAYOUT_FACTOR = 0.70     # 70% loss coverage
    
    def __init__(self):
        init_db()

    def get_pool_status(self) -> Dict[str, float]:
        """Retrieves current pool balance, active coverage, reserve threshold, and ICR."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT total_pool_balance, total_active_coverage, minimum_reserve_threshold, incurred_claim_ratio FROM pool_financials ORDER BY record_id DESC LIMIT 1;")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "total_pool_balance": float(row["total_pool_balance"]),
                "total_active_coverage": float(row["total_active_coverage"]),
                "minimum_reserve_threshold": float(row["minimum_reserve_threshold"]),
                "incurred_claim_ratio": float(row["incurred_claim_ratio"])
            }
        return {
            "total_pool_balance": 4287500.0,
            "total_active_coverage": 6750000.0,
            "minimum_reserve_threshold": 2025000.0,
            "incurred_claim_ratio": 0.65
        }

    def check_pool_reserve_gate(self, proposed_payout: float) -> Tuple[bool, str, Dict[str, float]]:
        """
        Evaluates 30% Minimum Reserve Rule:
        If total_pool_balance - proposed_payout < 30% of total_active_coverage:
        Queue claim for next cycle (Gate FAIL), else execute immediate payout (Gate PASS).
        """
        status = self.get_pool_status()
        current_balance = status["total_pool_balance"]
        active_coverage = status["total_active_coverage"]
        min_reserve = active_coverage * self.MINIMUM_RESERVE_RATIO
        
        balance_after = current_balance - proposed_payout
        
        if balance_after >= min_reserve:
            return True, "PASS", status
        else:
            return False, "QUEUED_DUE_TO_POOL_RESERVE", status

    def calculate_actuarial_premium(self, w_avg: float, risk_score: float, is_monsoon: bool, ncd_pct: float, claim_loading_pct: float) -> Dict[str, float]:
        """
        Computes weekly premium following official 8-Step Formula Chain:
        1. W_avg
        2. Coverage = 1.5 * W_avg
        3. Monthly Base Premium = 5% of Coverage
        4. Weekly Base Premium = Monthly Premium / 4
        5. AI Risk Adjustment = Weekly Base * (1 + risk_score)
        6. Seasonal Loading = * (1 + 0.35 if is_monsoon else 1.0)
        7. NCD Discount = * (1 - ncd_pct / 100.0)
        8. Claim Loading = * (1 + claim_loading_pct / 100.0)
        Clamped between IRDAI regulatory floor and 3x ceiling.
        """
        coverage = round(1.5 * w_avg, 2)
        monthly_base = 0.05 * coverage
        weekly_base = monthly_base / 4.0
        
        # Step 5: AI Risk Adjustment (0 to 0.5)
        adj_risk = weekly_base * (1.0 + min(0.5, max(0.0, risk_score)))
        
        # Step 6: Seasonal Loading (+35% during high monsoon)
        adj_seasonal = adj_risk * (1.35 if is_monsoon else 1.0)
        
        # Step 7: NCD Discount (max 20%)
        effective_ncd = min(20.0, max(0.0, ncd_pct))
        adj_ncd = adj_seasonal * (1.0 - effective_ncd / 100.0)
        
        # Step 8: Claim Loading (+5%, +12%, +25%)
        final_uncapped = adj_ncd * (1.0 + claim_loading_pct / 100.0)
        
        # Regulatory Floor & Ceiling Clamping
        # Floor = max(20.0, W_avg * 1.5 * 0.035 / 4), Ceiling = min(150.0, floor * 3)
        floor_rate = max(20.00, round(w_avg * 1.5 * 0.035 / 4.0, 2))
        ceiling_rate = min(150.00, max(floor_rate, round(floor_rate * 3.0, 2)))
        
        clamped_premium = round(max(floor_rate, min(ceiling_rate, final_uncapped)), 2)
        
        return {
            "w_avg": w_avg,
            "coverage_amount": coverage,
            "weekly_base_premium": round(weekly_base, 2),
            "final_weekly_premium": clamped_premium,
            "regulatory_floor": floor_rate,
            "regulatory_ceiling": ceiling_rate
        }

if __name__ == "__main__":
    engine = MutualPoolEngine()
    print("Pool Status:", engine.get_pool_status())
    pass_gate, gate_msg, _ = engine.check_pool_reserve_gate(2422.70)
    print(f"Reserve Gate Test (Payout Rs 2,422.70): {gate_msg} (Passed: {pass_gate})")
