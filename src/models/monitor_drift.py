import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd
import numpy as np
import subprocess

def calculate_psi(baseline: np.ndarray, current: np.ndarray, num_buckets=10) -> float:
    """Calculates Population Stability Index (PSI) between baseline training data and live inference data."""
    baseline = baseline[~np.isnan(baseline)]
    current = current[~np.isnan(current)]
    
    if len(baseline) == 0 or len(current) == 0:
        return 0.0

    percentiles = np.linspace(0, 100, num_buckets + 1)
    buckets = np.percentile(baseline, percentiles)
    buckets[0] -= 1e-5
    buckets[-1] += 1e-5

    base_counts, _ = np.histogram(baseline, bins=buckets)
    curr_counts, _ = np.histogram(current, bins=buckets)

    base_pct = base_counts / len(baseline)
    curr_pct = curr_counts / len(current)

    # Avoid zero division
    base_pct = np.where(base_pct == 0, 1e-4, base_pct)
    curr_pct = np.where(curr_pct == 0, 1e-4, curr_pct)

    psi = np.sum((curr_pct - base_pct) * np.log(curr_pct / base_pct))
    return round(float(psi), 4)

def check_data_drift():
    """Monitors dataset drift across environmental disruption features."""
    print("\n--- Executing Stage 5: Data Drift & Operational Health Monitoring ---")

    baseline_path = os.path.join("data", "processed", "pricing_dataset.csv")
    if not os.path.exists(baseline_path):
        print("Baseline dataset missing. Skipping drift monitor.")
        return False

    df_base = pd.read_csv(baseline_path)

    # Simulate recent inference batch with weather anomaly (monsoon surge)
    df_inference = df_base.copy()
    df_inference["weekly_total_rainfall_mm"] *= np.random.uniform(1.2, 1.8, len(df_inference))
    df_inference["weekly_avg_aqi"] *= np.random.uniform(1.1, 1.4, len(df_inference))

    # Calculate PSI on key disruption features
    psi_rain = calculate_psi(df_base["weekly_total_rainfall_mm"].values, df_inference["weekly_total_rainfall_mm"].values)
    psi_aqi = calculate_psi(df_base["weekly_avg_aqi"].values, df_inference["weekly_avg_aqi"].values)

    print(f"Feature Drift Monitoring Results:")
    print(f"  - Rainfall Feature PSI: {psi_rain} (Threshold: 0.25)")
    print(f"  - AQI Feature PSI: {psi_aqi} (Threshold: 0.25)")

    drift_detected = psi_rain > 0.25 or psi_aqi > 0.25

    if drift_detected:
        print("\n[WARNING] DATA DRIFT DETECTED! Triggering automated MLOps continuous retraining pipeline...")
        cmd = [
            sys.executable,
            "src/models/run_stage3_pipeline.py"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print("[PASSED] Continuous Retraining Completed! Models updated and re-registered in MLflow Registry.")
        else:
            print(f"Retraining error: {res.stderr}")
    else:
        print("[PASSED] Data distribution stable. No retraining required.")

    return True

if __name__ == "__main__":
    check_data_drift()
