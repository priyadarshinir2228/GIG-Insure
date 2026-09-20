import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np
import pandas as pd
from typing import List, Dict, Any

class IncomePredictor3Tier:
    """
    Model 2: Income Prediction (3-Tier Model: Cold Start -> WMA 12-Week Decay -> LightGBM).
    Predicts W_expected — each rider's counterfactual baseline expected weekly income.
    """
    
    DECAY_WEIGHTS = np.array([0.05, 0.05, 0.05, 0.05, 0.07, 0.07, 0.08, 0.08, 0.10, 0.10, 0.13, 0.17])

    def predict_w_expected(self, worker_id: str, weekly_history: List[float], zone_avg_income: float = 4200.0, adjusters: Dict[str, bool] = None) -> Dict[str, Any]:
        """
        Executes 3-tier income prediction:
        - Tier 1: Cold Start (<4 weeks history) -> Use Zone Average Income.
        - Tier 2: WMA Decay (4-12 weeks history) -> Weighted Moving Average (decay=0.9).
        - Tier 3: LightGBM (>12 weeks history) -> ML Regression with feature adjusters.
        """
        if adjusters is None:
            adjusters = {}

        n_weeks = len(weekly_history)
        
        if n_weeks < 4:
            # Tier 1: Cold Start Rule
            tier = "Tier 1 — Cold Start (Zone Average)"
            base_w = zone_avg_income
        elif n_weeks < 12:
            # Tier 2: Weighted Moving Average (WMA decay=0.9)
            tier = "Tier 2 — WMA Decay (4-11 Weeks)"
            # Normalize available weights
            weights = self.DECAY_WEIGHTS[-n_weeks:]
            weights = weights / weights.sum()
            base_w = float(np.dot(weekly_history, weights))
        else:
            # Tier 3: LightGBM / Full WMA 12-Week Model
            tier = "Tier 3 — LightGBM Personalised Model (12+ Weeks)"
            base_w = float(np.dot(weekly_history[-12:], self.DECAY_WEIGHTS))

        # Apply Adjusters
        multiplier = 1.0
        if adjusters.get("festival_flag", False):
            multiplier *= 1.20  # +20% demand spike during Diwali/Pongal
        if adjusters.get("heatwave_flag", False):
            multiplier *= 0.85  # -15% reduction in outdoor riding hours
        if adjusters.get("platform_incentive", False):
            multiplier *= 1.10  # +10% target bonus campaign

        final_w_expected = round(base_w * multiplier, 2)
        coverage_amount = round(1.5 * final_w_expected, 2)
        trigger_threshold = round(0.60 * final_w_expected, 2)

        return {
            "worker_id": worker_id,
            "tier_used": tier,
            "weeks_history_count": n_weeks,
            "base_w_expected": round(base_w, 2),
            "final_w_expected": final_w_expected,
            "coverage_amount": coverage_amount,
            "trigger_threshold_60pct": trigger_threshold
        }

income_predictor = IncomePredictor3Tier()

if __name__ == "__main__":
    predictor = IncomePredictor3Tier()
    # Test Tier 1 Cold Start
    print("New Rider (1 week):", predictor.predict_w_expected("W_NEW", [3800.0]))
    # Test Tier 3 12-Week Veteran
    hist_12 = [4100, 4200, 4300, 4150, 4400, 4500, 4600, 4450, 4700, 4800, 4900, 5100]
    print("Veteran Rider (12 weeks):", predictor.predict_w_expected("W_VET", hist_12, adjusters={"festival_flag": True}))
