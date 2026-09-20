import os
import pandas as pd
import numpy as np

def build_feature_pipeline():
    """Constructs engineered features for ML models (Dynamic Pricing & Fraud Detection)."""
    print("Executing Feature Engineering Pipeline...")
    
    proc_dir = os.path.join("data", "processed")
    
    # Load preprocessed datasets
    df_env = pd.read_csv(os.path.join(proc_dir, "processed_environmental.csv"))
    df_workers = pd.read_csv(os.path.join(proc_dir, "processed_workers.csv"))
    df_orders = pd.read_csv(os.path.join(proc_dir, "processed_orders.csv"))
    df_claims = pd.read_csv(os.path.join(proc_dir, "processed_claims.csv"))

    # 1. Join Orders with Worker Persona Features
    df_master = pd.merge(df_orders, df_workers, on=["worker_id", "zone_id"], how="inner")

    # 2. Join with Weekly Environmental Disruption Features
    df_master = pd.merge(df_master, df_env, on=["zone_id", "week_start_date"], how="inner")

    # 3. Construct Feature 1: Zone Disruption Risk Index (R_i)
    # Normalized score between 0.0 (safe zone) and 1.0 (high disruption risk)
    df_master["zone_disruption_risk_index"] = (
        (df_master["weekly_total_rainfall_mm"] / 200.0) * 0.45 +
        (df_master["weekly_avg_aqi"] / 400.0) * 0.30 +
        (df_master["zone_closure_days_count"] / 3.0) * 0.25
    ).clip(0.0, 1.0).round(4)

    # 4. Construct Feature 2: Seasonal Monsoon Loading Multiplier (+0% to +50%)
    df_master["monsoon_loading"] = np.where(
        df_master["is_monsoon"] == 1,
        1.0 + (df_master["weekly_total_rainfall_mm"] / 300.0) * 0.50,
        1.0
    ).round(3)

    # 5. Construct Feature 3: Target Dynamic Weekly Premium Calculation (Pricing Target Variable)
    # Base weekly rate ₹35.0, adjusted by zone risk, vehicle risk, and monsoon loading
    base_premium = 35.0
    df_master["target_dynamic_weekly_premium"] = (
        base_premium * (1.0 + df_master["zone_disruption_risk_index"]) * 
        df_master["vehicle_risk_factor"] * df_master["monsoon_loading"]
    ).round(2).clip(29.0, 79.0)

    # Save Master Features
    master_path = os.path.join(proc_dir, "master_features.csv")
    df_master.to_csv(master_path, index=False)
    print(f"Saved Master Feature Dataset to {master_path} ({len(df_master)} rows)")

    # 6. Construct Pricing Model Training Dataset
    pricing_features = [
        "worker_id", "zone_id", "week_start_date", "zone_tier_code",
        "tenure_days", "vehicle_risk_factor", "is_full_time",
        "avg_active_hours_per_week", "historical_weekly_income",
        "weekly_total_rainfall_mm", "weekly_max_temp_celsius",
        "weekly_avg_aqi", "zone_closure_days_count", "is_monsoon",
        "zone_disruption_risk_index", "monsoon_loading",
        "target_dynamic_weekly_premium"
    ]
    df_pricing = df_master[pricing_features].drop_duplicates()
    pricing_path = os.path.join(proc_dir, "pricing_dataset.csv")
    df_pricing.to_csv(pricing_path, index=False)
    print(f"Saved Dynamic Pricing Dataset to {pricing_path} ({len(df_pricing)} rows)")

    # 7. Construct Fraud Detection Training Dataset (Join with Claims Stream)
    df_fraud = pd.merge(df_claims, df_master[[
        "worker_id", "zone_id", "week_start_date",
        "earnings_loss_amount", "disruption_impact_ratio",
        "zone_disruption_risk_index", "historical_weekly_income"
    ]], on=["worker_id", "zone_id", "week_start_date"], how="inner")

    # Construct Composite Fraud Signals
    df_fraud["gps_anomaly_flag"] = (df_fraud["gps_deviation_score"] > 12.0).astype(int)
    df_fraud["syndicate_device_flag"] = (df_fraud["device_id_reuse_count"] > 3).astype(int)
    df_fraud["timing_gap_anomaly_flag"] = (df_fraud["claim_vs_event_gap_minutes"] > 360).astype(int)

    fraud_features = [
        "claim_id", "worker_id", "zone_id", "week_start_date",
        "gps_deviation_score", "device_id_reuse_count",
        "claim_vs_event_gap_minutes", "claims_per_worker_per_month",
        "claimed_amount", "earnings_loss_amount", "disruption_impact_ratio",
        "zone_disruption_risk_index", "gps_anomaly_flag",
        "syndicate_device_flag", "timing_gap_anomaly_flag", "is_fraud_label"
    ]
    df_fraud_dataset = df_fraud[fraud_features]
    fraud_path = os.path.join(proc_dir, "fraud_dataset.csv")
    df_fraud_dataset.to_csv(fraud_path, index=False)
    print(f"Saved Intelligent Fraud Dataset to {fraud_path} ({len(df_fraud_dataset)} rows)")

    print("[PASSED] Stage 2 Feature Engineering Pipeline Complete!")
    return df_pricing, df_fraud_dataset

if __name__ == "__main__":
    build_feature_pipeline()
